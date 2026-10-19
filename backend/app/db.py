"""SQLite: схема, подключение, запись событий.

Все события идут в одну таблицу events — из неё считается вся
воронка (метрики в routers/stats.py). Лиды и заявки дублируются
в отдельные таблицы для удобной выгрузки.
"""
import sqlite3
from contextlib import closing, contextmanager
from datetime import datetime, timezone
from typing import Any

from .config import DATA_DIR, settings

DB_FILE = DATA_DIR / "aistudio.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT    NOT NULL,
    session_id  TEXT,
    name        TEXT    NOT NULL,
    response_ms INTEGER,
    props       TEXT
);
CREATE INDEX IF NOT EXISTS idx_events_name_ts ON events(name, ts);
CREATE INDEX IF NOT EXISTS idx_events_session ON events(session_id);

CREATE TABLE IF NOT EXISTS leads (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT    NOT NULL,
    source      TEXT    NOT NULL,            -- quiz | contact | chat
    quiz_type   TEXT,
    email       TEXT,
    name        TEXT,
    phone       TEXT,
    company     TEXT,
    industry    TEXT,
    revenue     TEXT,
    score_pct   INTEGER,
    intent      TEXT,                        -- для чат-бота: consultation|demo|info
    session_id  TEXT,                        -- сессия чата для атрибуции «контакт → аудит»
    payload     TEXT,
    report_id   TEXT
);
CREATE INDEX IF NOT EXISTS idx_leads_ts ON leads(ts);

CREATE TABLE IF NOT EXISTS chat_messages (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    ts         TEXT NOT NULL,
    session_id TEXT NOT NULL,
    role       TEXT NOT NULL,                -- user | assistant
    content    TEXT NOT NULL,
    response_ms INTEGER
);
CREATE INDEX IF NOT EXISTS idx_chat_session ON chat_messages(session_id, id);
"""


@contextmanager
def get_conn():
    """Отдаёт соединение с авто-коммитом; закрывает его на выходе."""
    conn = sqlite3.connect(DB_FILE, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(SCHEMA)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def log_event(
    name: str,
    session_id: str | None = None,
    response_ms: int | None = None,
    **props: Any,
) -> None:
    """Универсальная точка записи событий воронки."""
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO events (ts, session_id, name, response_ms, props) VALUES (?,?,?,?,?)",
            (now_iso(), session_id, name, response_ms, _json(props)),
        )


def create_lead(**cols: Any) -> int:
    cols = {"ts": now_iso(), **cols}
    with get_conn() as conn:
        cur = conn.execute(
            f"INSERT INTO leads ({', '.join(cols)}) VALUES ({', '.join(['?'] * len(cols))})",
            tuple(cols.values()),
        )
        return cur.lastrowid


def _json(obj: Any) -> str | None:
    if not obj:
        return None
    import json

    return json.dumps(obj, ensure_ascii=False)


init_db()