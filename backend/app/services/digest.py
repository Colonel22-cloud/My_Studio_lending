"""Ежедневный email-дайджест метрик менеджеру.

Планировщик запускается в main.py (lifespan): раз в день в DIGEST_HOUR
по Москвы собирает метрики за последние сутки (и за 7 дней для тренда)
и отправляет письмо на MANAGER_EMAIL.

Пока SMTP не настроено — текст дайджеста пишется в лог, чтобы дайджест
можно было проверять без почты.
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

from ..config import settings
from . import emailer, metrics

log = logging.getLogger("digest")

MSK = timezone(timedelta(hours=3))


def build_digest_text() -> tuple[str, str]:
    """(subject, text) письма. Метрики за сутки + за 7 дней (для тренда)."""
    s1 = metrics.collect_stats(days=1)
    s7 = metrics.collect_stats(days=7)

    t1, f1 = s1["totals"], s1["funnel"]
    f7 = s7["funnel"]

    def pct(v: float | None) -> str:
        return f"{v}%" if v is not None else "—"

    lines = [
        f"Дайджест AI Studio за {datetime.now(MSK).strftime('%d.%m.%Y')} (последние 24 часа)",
        "",
        "## Диалоги и лиды",
        f"• Диалогов с ботом стартовано: {t1['dialogs'] or 0}",
        f"• Диалогов, в которых оставлены контакты: {t1['leads_chat'] or 0}",
        f"• Доля диалогов со сбором контактов: {pct(f1['lead_capture_rate'])}"
        f"   [цель 15–25%]",
        f"• Квизов запущено: {t1['quizzes'] or 0} (из чата: {t1['quizzes_from_chat'] or 0})",
        f"• Контакты → аудит: {pct(f1['lead_to_audit_rate'])}   [цель 30–40%]",
        f"• Аудит → консультация: {pct(f1['audit_to_consultation_rate'])}   [цель 10–15%]",
        "",
        "## Скорость ответа бота",
        f"• Среднее время ответа: {round(t1['avg_response_ms'] or 0)} мс",
        f"• 95-й процентиль: {round(t1['p95_response_ms'] or 0)} мс",
        "",
        "## Тренд за 7 дней",
        f"• Доля диалогов со сбором контактов: {pct(f7['lead_capture_rate'])}",
        f"• Контакты → аудит: {pct(f7['lead_to_audit_rate'])}",
        f"• Аудит → консультация: {pct(f7['audit_to_consultation_rate'])}",
        f"• Лидов из чата за 7 дней: {s7['totals']['leads_chat'] or 0}",
        f"• Аудитов за 7 дней: {s7['totals']['quizzes'] or 0}",
    ]
    return "AI Studio — дайджест метрик за сутки", "\n".join(lines)


async def send_digest() -> bool:
    subject, text = build_digest_text()
    if not settings.smtp_configured or not settings.manager_email:
        log.warning("SMTP/MANAGER_EMAIL не заданы — дайджест не отправлен:\n%s", text)
        return False
    ok = await emailer.send_report_email(settings.manager_email, subject, text)
    log.info("Дайджест: %s", "отправлен" if ok else "не отправлен")
    return ok


def _seconds_until(hour: int, now: datetime | None = None) -> float:
    """Сколько секунд ждать до ближайшего запуска в `hour`:00 MSK."""
    now = now or datetime.now(MSK)
    run = now.replace(hour=hour % 24, minute=5, second=0, microsecond=0)
    if run <= now:
        run += timedelta(days=1)
    return (run - now).total_seconds()


async def scheduler_loop() -> None:
    """Фоновая задача: раз в сутки в DIGEST_HOUR (по МСК) — send_digest()."""
    hour = settings.digest_hour
    log.info("Дайджест: запуск ежедневно в %02d:05 МСК", hour % 24)
    while True:
        await asyncio.sleep(_seconds_until(hour))
        try:
            await send_digest()
        except Exception:  # noqa: BLE001  — дайджест не должен ронять сервис
            log.exception("Ошибка при отправке дайджеста")