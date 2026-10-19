"""Расчёт метрик воронки. Общий модуль: им пользуются роутер /api/stats
и ежедневный email-дайджест менеджеру (services/digest.py).

Целевые значения:
  диалогов в день                  20–50
  доля диалогов со сбором контактов 15–25%
  контакты → аудит                 30–40%
  аудит → консультация             10–15%
  среднее время ответа бота        —
"""
from datetime import datetime, timedelta, timezone

from ..db import get_conn


def collect_stats(days: int = 1) -> dict:
    """Все метрики за последние `days` дней. Единая точка правды."""
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(timespec="seconds")
    with get_conn() as conn:
        periods = _daily_dialogs(conn, days)
        totals = {
            "dialogs": _count_dialogs(conn, since),
            "sessions": _count_sessions(conn, since),
            "leads_chat": _scalar(conn, "SELECT COUNT(*) c FROM leads WHERE ts>? AND source='chat'", since),
            "chats_with_lead": _scalar(
                conn,
                "SELECT COUNT(DISTINCT session_id) c FROM events "
                "WHERE ts>? AND name='lead_captured'",
                since,
            ),
            "quizzes": _scalar(conn, "SELECT COUNT(*) c FROM leads WHERE ts>? AND source='quiz'", since),
            "quizzes_from_chat": _scalar(
                conn,
                "SELECT COUNT(*) c FROM leads WHERE ts>? AND source='quiz' AND session_id IS NOT NULL",
                since,
            ),
            "consultations": _scalar(
                conn,
                "SELECT COUNT(DISTINCT session_id) c FROM events WHERE ts>? AND name='lead_captured' "
                "AND json_extract(props,'$.intent')='consultation'",
                since,
            ),
            "avg_response_ms": _scalar(
                conn,
                "SELECT AVG(response_ms) v FROM events WHERE ts>? AND name='chat_reply' AND response_ms>0",
                since,
            ),
            "p95_response_ms": _p95(conn, since),
        }

    dialogs = totals["dialogs"] or 0
    chat_leads = totals["leads_chat"] or 0
    quizzes_from_chat = totals["quizzes_from_chat"] or 0
    quizzes = totals["quizzes"] or 0
    cons = totals["consultations"] or 0

    return {
        "period_days": days,
        "daily_dialogs": periods,
        "totals": totals,
        "funnel": {
            "lead_capture_rate": round(chat_leads / dialogs * 100, 1) if dialogs else None,
            "lead_to_audit_rate": round(quizzes_from_chat / chat_leads * 100, 1) if chat_leads else None,
            "audit_to_consultation_rate": round(cons / quizzes * 100, 1) if quizzes else None,
        },
        "targets": {
            "dialogs_per_day": "20–50",
            "lead_capture_rate": "15–25%",
            "lead_to_audit_rate": "30–40%",
            "audit_to_consultation_rate": "10–15%",
        },
    }


def _daily_dialogs(conn, days: int) -> list[dict]:
    rows = conn.execute(
        "SELECT substr(ts,1,10) d, COUNT(DISTINCT session_id) v FROM events "
        "WHERE name='chat_reply' AND session_id IS NOT NULL GROUP BY d ORDER BY d DESC LIMIT ?",
        (days,),
    ).fetchall()
    return [{"date": r["d"], "dialogs": r["v"]} for r in rows]


def _count_dialogs(conn, since: str) -> int:
    return _scalar(
        conn,
        "SELECT COUNT(DISTINCT session_id) c FROM events "
        "WHERE name='chat_reply' AND session_id IS NOT NULL AND ts>?",
        since,
    )


def _count_sessions(conn, since: str) -> int:
    return _scalar(
        conn,
        "SELECT COUNT(DISTINCT session_id) c FROM events WHERE session_id IS NOT NULL AND ts>?",
        since,
    )


def _scalar(conn, sql: str, *params) -> float | None:
    row = conn.execute(sql, params).fetchone()
    val = row["c"] if "c" in row.keys() else (row["v"] if "v" in row.keys() else row[0])
    return val


def _p95(conn, since: str) -> float | None:
    rows = conn.execute(
        "SELECT response_ms v FROM events WHERE ts>? AND name='chat_reply' AND response_ms>0 ORDER BY v",
        (since,),
    ).fetchall()
    if not rows:
        return None
    idx = min(len(rows) - 1, int(len(rows) * 0.95))
    return rows[idx]["v"]