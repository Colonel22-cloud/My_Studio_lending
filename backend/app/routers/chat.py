"""POST /api/chat — чат-бот квалификации лидов.

Ответ бота собирается из трёх слоёв:
  1. системный промпт (System_prompt_Chat-bot.txt из корня проекта);
  2. RAG-контекст — топ-k фрагментов баз знаний по запросу (services/rag.py);
  3. протокол <LEAD> — модель помечает ответы, где посетитель передал
     контакты; бэкенд сохраняет лид и шлёт уведомление менеджеру.
"""
import asyncio
import json
import logging
import re
import time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..config import settings
from ..db import create_lead, get_conn, log_event, now_iso
from ..deps import verify_site_token
from ..rate_limit import check_rate_limit
from ..schemas import ChatRequest
from ..services import emailer, llm, rag

log = logging.getLogger("chat")
router = APIRouter(dependencies=[Depends(verify_site_token), Depends(check_rate_limit)])

CHAT_PROMPT_FILE = "System_prompt_Chat-bot.txt"

LEAD_PROTOCOL = """

# ПРОТОКОЛ ПЕРЕДАЧИ КОНТАКТОВ (техническое расширение, добавлено бэкендом)

Если Пользователь сообщил email ИЛИ телефон, и выразил готовность
к общению с экспертом (консультация, демо) — сделай так:
1. Кратко поблагодари и пообещай, что эксперт свяжется в ближайшее время.
2. В САМОМ КОНЦЕ ответа добавь служебный блок ровно в таком виде:
<LEAD>{"intent":"consultation","name":"...","phone":"...","email":"...","company":"..."}</LEAD>
intent: consultation (нужна консультация) | demo (хочет демо) | info (просто оставил контакты).
Заполняй только известные поля. Блок добавляй ТОЛЬКО если есть хотя бы email или телефон,
и ТОЛЬКО один раз за диалог на каждый новый набор контактов. Пользователь не должен
видеть текст внутри блока — для него это невидимый разделитель.

Если контактов пока нет — НЕ добавляй блок, просто веди диалог по сценариям.
"""

# Оффлайн-режим (LLM ключа нет): честные заглушки вместо падения
FALLBACK_REPLIES = [
    "Извините, я временно работаю в ограниченном режиме. "
    "Оставьте контакты через форму на странице «Контакты» — эксперт свяжется с вами.",
    "Сейчас я не могу дать полноценный ответ. Пройдите бесплатный экспресс-аудит — "
    "он покажет зоны роста вашей компании: <аудит эффективности> или <аудит рисков>.",
]

_LEAD_RE = re.compile(r"<LEAD>\s*(\{.*?\})\s*</LEAD>", re.DOTALL)


class ChatResponse(BaseModel):
    reply: str
    llm: bool = True  # False — ответ из оффлайн-заглушек


@router.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    t0 = time.perf_counter()
    history = _load_history(req.session_id)

    _store(req.session_id, "user", req.message)

    system = await _system_prompt(req.message)

    try:
        reply = await llm.chat_complete(
            system=system,
            user=req.message,
            history=history,
            max_tokens=800,
            temperature=0.6,
            model=settings.chat_llm_model or None,  # пусто -> основная модель
        )
        llm_used = True
    except llm.LLMNotConfigured:
        reply = FALLBACK_REPLIES[len(history) % len(FALLBACK_REPLIES)]
        llm_used = False
    except Exception:  # noqa: BLE001  сеть/квоты LLM
        log.exception("LLM ошибки в чате, сессия %s", req.session_id)
        raise HTTPException(status_code=503, detail="LLM недоступен")

    lead = _extract_lead(reply, req.session_id)
    if lead:
        asyncio.create_task(_notify_manager(lead, req.session_id))

    # <LEAD>-блок пользователь не должен увидеть
    reply = _LEAD_RE.sub("", reply).strip()

    response_ms = int((time.perf_counter() - t0) * 1000)
    _store(req.session_id, "assistant", reply, response_ms=response_ms)
    log_event(
        "chat_reply", session_id=req.session_id,
        response_ms=response_ms, llm=llm_used, rag=bool(_rag_ready()),
    )
    return ChatResponse(reply=reply, llm=llm_used)


def _rag_ready() -> bool:
    idx = rag.load_index()
    return bool(idx and idx["chunks"])


async def _system_prompt(user_message: str) -> str:
    base = llm.load_prompt(CHAT_PROMPT_FILE)

    parts = [base, LEAD_PROTOCOL]
    if _rag_ready():
        try:
            context = await rag.search(user_message)
            if context:
                parts.append(
                    "\n\n# ФРАГМЕНТЫ БАЗЫ ЗНАНИЙ (актуальные для запроса)\n"
                    "Отвечай фактами из них, если они уместны. Не выдумывай цены и факты,\n"
                    "которых нет в фрагментах и системном промпте:\n\n" + context
                )
        except Exception:  # noqa: BLE001  недоступен RAG — отвечаем без контекста
            log.exception("RAG search failed")
    return "\n".join(parts)


def _extract_lead(reply: str, session_id: str) -> dict | None:
    m = _LEAD_RE.search(reply or "")
    if not m:
        return None
    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError:
        log.warning("Некорректный <LEAD> блок: %s", m.group(1)[:200])
        return None
    if not (data.get("email") or data.get("phone")):
        return None

    lead_id = create_lead(
        source="chat",
        email=data.get("email"),
        name=data.get("name"),
        phone=data.get("phone"),
        company=data.get("company"),
        intent=(data.get("intent") or "info").lower(),
        session_id=session_id,
        payload=json.dumps(data, ensure_ascii=False),
    )
    log_event("lead_captured", session_id=session_id, intent=data.get("intent"), lead_id=lead_id)
    log.info("Лид из чата #%s (сессия %s)", lead_id, session_id)
    return {**data, "lead_id": lead_id}


async def _notify_manager(lead: dict, session_id: str) -> None:
    await emailer.notify_manager(
        subject=f"🔥 Контакты из чат-бота (intent: {lead.get('intent', 'info')})",
        text=(
            f"Имя: {lead.get('name') or '—'}\n"
            f"Компания: {lead.get('company') or '—'}\n"
            f"Email: {lead.get('email') or '—'}\n"
            f"Телефон: {lead.get('phone') or '—'}\n"
            f"Интент: {lead.get('intent', 'info')}\n"
            f"Сессия диалога: {session_id}\n"
            f"Lead ID: {lead.get('lead_id')}"
        ),
    )


def _load_history(session_id: str) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT role, content FROM chat_messages WHERE session_id=? ORDER BY id",
            (session_id,),
        ).fetchall()
    return [{"role": r["role"], "content": r["content"]} for r in rows]


def _store(session_id: str, role: str, content: str, response_ms: int | None = None) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO chat_messages (ts, session_id, role, content, response_ms) VALUES (?,?,?,?,?)",
            (now_iso(), session_id, role, content, response_ms),
        )


# --- Ручная фиксация собранных контактов (чат-бот передаёт менеджеру) ---
class ChatLead(BaseModel):
    session_id: str
    email: str | None = None
    name: str | None = None
    phone: str | None = None
    company: str | None = None
    intent: str = "info"  # consultation | demo | info


@router.post("/api/chat/lead")
async def chat_lead(lead: ChatLead, _=Depends(verify_site_token)) -> dict:
    from ..db import create_lead

    lead_id = create_lead(
        source="chat",
        email=lead.email,
        name=lead.name,
        phone=lead.phone,
        company=lead.company,
        intent=lead.intent,
        session_id=lead.session_id,
        payload=json.dumps(lead.model_dump(), ensure_ascii=False),
    )
    log_event("lead_captured", session_id=lead.session_id, intent=lead.intent, lead_id=lead_id)

    import asyncio

    asyncio.create_task(emailer.notify_manager(
        subject=f"🔥 Горячий лид из чат-бота (intent: {lead.intent})",
        text=(
            f"Сессия: {lead.session_id}\n"
            f"Имя: {lead.name or '—'}\n"
            f"Компания: {lead.company or '—'}\n"
            f"Email: {lead.email or '—'}\n"
            f"Телефон: {lead.phone or '—'}\n"
            f"Интент: {lead.intent}"
        ),
    ))
    return {"ok": True, "lead_id": lead_id}


if not settings.llm_configured:
    log.warning("LLM не настроен — чат-бот работает в оффлайн-режиме заглушек")