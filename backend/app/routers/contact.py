"""POST /api/contact — форма contacts.html."""
import asyncio
import logging

from fastapi import APIRouter, Depends

from ..db import create_lead, log_event
from ..deps import verify_site_token
from ..rate_limit import check_rate_limit
from ..schemas import ContactSubmission
from ..services import emailer

log = logging.getLogger("contact")
router = APIRouter(dependencies=[Depends(verify_site_token), Depends(check_rate_limit)])


@router.post("/api/contact")
async def submit_contact(sub: ContactSubmission) -> dict:
    # Honeypot: скрытое поле «website» реально заполняют только боты —
    # боту отвечаем как об успехе, заявку молча выбрасываем.
    if sub.website.strip():
        log_event("spam_blocked", hp_website=sub.website[:120])
        log.warning("Форма контактов: honeypot заполнен — заявка отброшена")
        return {"ok": True, "lead_id": 0}

    lead_id = create_lead(
        source="contact",
        email=sub.email,
        name=sub.name,
        phone=sub.phone,
        company=sub.company,
        industry=sub.industry,
        payload=str(sub.model_dump()),
    )
    log_event("contact_submitted", lead_id=lead_id, src=sub.source)

    asyncio.create_task(_manager_notification(sub, lead_id))
    return {"ok": True, "lead_id": lead_id}


async def _manager_notification(sub: ContactSubmission, lead_id: int) -> None:
    await emailer.notify_manager(
        subject=f"📋 Заявка с формы контактов — {sub.name}",
        text=(
            f"Имя: {sub.name}\n"
            f"Компания: {sub.company or '—'}\n"
            f"Email: {sub.email}\n"
            f"Телефон: {sub.phone or '—'}\n"
            f"Сфера: {sub.industry or '—'}\n"
            f"Задача: {sub.message or '—'}\n"
            f"Источник: {sub.source or 'форма контактов'}\n"
            f"Lead ID: {lead_id}"
        ),
    )