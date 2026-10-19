"""OpenAI-совместимый клиент LLM (YandexGPT / GigaChat — определяется LLM_BASE_URL).

Если ключа нет — все вызовы падают в LLMNotConfigured, роутеры обязаны
давать graceful-ответ (сайт при этом продолжает работать standalone).
"""
import httpx

from ..config import settings

CHAT_TIMEOUT = settings.llm_timeout


class LLMNotConfigured(Exception):
    pass


def _messages(system: str, history: list[dict], user: str) -> list[dict]:
    msgs: list[dict] = [{"role": "system", "content": system}]
    msgs += history[-12:]  # окно контекста диалога
    msgs.append({"role": "user", "content": user})
    return msgs


async def chat_complete(
    system: str,
    user: str,
    history: list[dict] | None = None,
    *,
    max_tokens: int = 4000,
    temperature: float | None = None,
    model: str | None = None,
) -> str:
    """Возвращает текст ответа модели. history — [{role, content}, ...].

    model: можно задать другую модель вызова (наш случай — дешёвая
    yandexgpt-lite для чата и большая для отчётов). По умолчанию LLM_MODEL.
    """
    if not settings.llm_configured:
        raise LLMNotConfigured("LLM_BASE_URL/LLM_API_KEY не заданы")

    payload = {
        "model": model or settings.llm_model,
        "messages": _messages(system, history or [], user),
        "temperature": settings.llm_temperature if temperature is None else temperature,
        "max_tokens": max_tokens,
    }
    headers = {"Authorization": f"{settings.llm_auth_scheme} {settings.llm_api_key}"}

    async with httpx.AsyncClient(timeout=CHAT_TIMEOUT) as client:
        resp = await client.post(
            f"{settings.llm_base_url.rstrip('/')}/chat/completions",
            json=payload,
            headers=headers,
        )
        resp.raise_for_status()
        data = resp.json()

    return data["choices"][0]["message"]["content"]


def load_prompt(filename: str) -> str:
    """Читает системный промпт из PROMPTS_DIR (корень проекта)."""
    path = settings.prompts_dir / filename
    text = path.read_text(encoding="utf-8")
    # Файлы обёрнуты в маркеры === НАЧАЛО/КОНЕЦ === — срезаем их
    start, end = text.find("=== НАЧАЛО"), text.find("=== КОНЕЦ")
    if start != -1 and end != -1:
        text = text[text.find("\n", start) + 1 : end]
    return text.strip()