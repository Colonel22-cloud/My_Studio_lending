"""Отправка почты через SMTP (Yandex 360 / Mail.ru).

Пока SMTP не настроен — письма не отправляются, но факт логируется,
чтобы конвейер отчётов можно было тестировать до появления почты
на домене.
"""
import asyncio
import logging
import smtplib
from email.message import EmailMessage
from pathlib import Path

from ..config import settings

log = logging.getLogger("emailer")


async def send_report_email(
    to_email: str,
    subject: str,
    body_text: str,
    pdf_path: Path | None = None,
    pdf_name: str = "Отчёт.pdf",
) -> bool:
    """Письмо клиенту с вложенным PDF-отчётом. True — отправлено."""
    if not settings.smtp_configured:
        log.warning(
            "SMTP не настроен — письмо для %s не отправлено (PDF: %s)",
            to_email, pdf_path or "нет",
        )
        return False

    msg = EmailMessage()
    msg["From"] = settings.email_from
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body_text)

    if pdf_path and pdf_path.exists():
        msg.add_attachment(
            pdf_path.read_bytes(),
            maintype="application",
            subtype="pdf",
            filename=pdf_name,
        )

    await asyncio.to_thread(_send_smtp, msg)
    log.info("Письмо отправлено: %s -> %s", subject, to_email)
    return True


async def notify_manager(text: str, subject: str = "🔥 Горячий лид с сайта") -> bool:
    """Уведомление менеджеру о лиде (email российского провайдера)."""
    if not settings.smtp_configured or not settings.manager_email:
        log.warning("Уведомление менеджеру не отправлено:\n%s", text)
        return False
    return await send_report_email(settings.manager_email, subject, text)


def _send_smtp(msg: EmailMessage) -> None:
    if settings.smtp_port == 465:
        with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=30) as s:
            s.login(settings.smtp_user, settings.smtp_password)
            s.send_message(msg)
    else:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as s:
            s.starttls()
            s.login(settings.smtp_user, settings.smtp_password)
            s.send_message(msg)