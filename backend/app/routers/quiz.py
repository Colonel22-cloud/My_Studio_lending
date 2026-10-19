"""POST /api/quiz — приём ответов квиза, лид, отчёт, уведомление менеджера."""
import logging
import uuid

from fastapi import APIRouter, Depends

from ..db import create_lead, log_event
from ..deps import verify_site_token
from ..rate_limit import check_rate_limit
from ..schemas import QuizSubmission
from ..services import emailer, report

log = logging.getLogger("quiz")
router = APIRouter(dependencies=[Depends(verify_site_token), Depends(check_rate_limit)])

QUIZ_TITLES = {
    "efficiency": "аудит эффективности",
    "security": "аудит управления рисками",
}


@router.post("/api/quiz")
async def submit_quiz(sub: QuizSubmission) -> dict:
    # Honeypot: скрытое поле «website» реально заполняют только боты.
    # Боту отвечаем как о успехе, но ничего не сохраняем и не считаем.
    if sub.website.strip():
        log_event("spam_blocked", quiz_type=sub.quiz, hp_website=sub.website[:120])
        log.warning("Квиз: honeypot заполнен — заявка отброшена")
        return {"ok": True, "report_id": ""}

    report_id = uuid.uuid4().hex[:12]
    data = sub.model_dump()

    lead_id = create_lead(
        source="quiz",
        quiz_type=sub.quiz,
        email=sub.email,
        name=sub.name,
        phone=sub.phone,
        industry=sub.industry,
        revenue=sub.revenue,
        score_pct=sub.pct,
        session_id=sub.session_id,
        report_id=report_id,
        payload=str(data),
    )
    log_event(
        "quiz_submitted", session_id=sub.session_id,
        quiz_type=sub.quiz, pct=sub.pct, lead_id=lead_id, report_id=report_id,
    )

    # Уведомление менеджеру — в фоновой задаче, ответ сайту не ждём
    import asyncio

    asyncio.create_task(_manager_notification(sub, report_id))

    pdf_path = None
    try:  # ошибки конвейера (нет ключа LLM/SMTP) не должны ронять API
        pdf_path = await report.build_and_save_pdf(sub.quiz, data, report_id)
    except Exception:  # noqa: BLE001  отчёт переотправим вручную, лид уже сохранён
        log.exception("Генерация отчёта %s упала", report_id)
        log_event("report_failed", quiz_type=sub.quiz, report_id=report_id)

    if pdf_path:
        try:
            await emailer.send_report_email(
                to_email=sub.email,
                subject="Ваш персональный отчёт по экспресс-аудиту",
                body_text=(
                    "Здравствуйте!\n\nВо вложении — ваш персональный отчёт по экспресс-аудиту.\n\n"
                    "ID отчёта: " + report_id + "\n\n"
                    "Если хотите обсудить результаты — просто ответьте на это письмо.\n\n"
                    "— AI Studio"
                ),
                pdf_path=pdf_path,
                pdf_name=f"Экспресс-аудит_{report_id}.pdf",
            )
            log_event("report_sent", report_id=report_id, to=sub.email)
        except Exception:  # noqa: BLE001
            log.exception("Отправка письма %s упала", report_id)
            log_event("report_email_failed", report_id=report_id)

    return {"ok": True, "report_id": report_id}


async def _manager_notification(sub: QuizSubmission, report_id: str) -> None:
    hot = "🔥" if sub.pct >= 50 or sub.phone else "📋"
    await emailer.notify_manager(
        subject=f"{hot} Квиз «{QUIZ_TITLES[sub.quiz]}» — {sub.pct}% от максимума",
        text=(
            f"Тип: {QUIZ_TITLES[sub.quiz]}\n"
            f"Балл: {sub.score}/{sub.maxScore} ({sub.pct}%)\n"
            f"Email: {sub.email}\n"
            f"Имя: {sub.name or '—'}\n"
            f"Телефон: {sub.phone or '—'}\n"
            f"Сфера: {sub.industry or '—'}\n"
            f"Оборот: {sub.revenue or '—'}\n"
            f"Пришёл из чат-бота: {'да, сессия ' + str(sub.session_id) if sub.session_id else 'нет'}\n"
            f"Report ID: {report_id}"
        ),
    )