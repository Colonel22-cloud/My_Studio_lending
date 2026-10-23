"""Смоук-тест: быстрая проверка всего конвейера в одну команду.

Запуск (в отдельном терминале, пока сервер работает):
  cd backend
  python scripts/smoke_test.py

Что проверяет:
  API (порт 8000):  health, чат-бот, квиз, форма, honeypot, rate-limit, метрики
  Сайт (порт 5500): страницы открываются, honeypot в разметке актуальной версии

Всё, что тест создаёт (лиды, диалоги, события), в конце удаляется —
метрики воронки остаются чистыми. Тестовые запросы идут с подставным
IP (X-Forwarded-For), чтобы не блокировать лимитами ваш реальный IP.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx  # noqa: E402

BASE_DIR = Path(__file__).resolve().parent.parent
API = "http://127.0.0.1:8000"
SITE = "http://localhost:5500"
TOKEN = ""
STAMP = str(int(time.time()))           # уникальная метка прогона
SESSION = f"smoke-{STAMP}"
# Тестовые IP (RFC 5737). Каждому прогону — свой адрес, чтобы лимиты
# rate-limit предыдущего прогона не портили следующий (окно — 1 час).
_BASE_IP = 1 + (int(STAMP) % 125) * 2     # три подряд адреса на прогон (≤ 251)
IP  = f"203.0.113.{_BASE_IP}"             # базовый тестовый IP
IP2 = f"203.0.113.{_BASE_IP + 1}"         # соседние — у каждого теста свой лимит
IP3 = f"203.0.113.{_BASE_IP + 2}"

results: list[tuple[bool, str]] = []
SMOKE_REPORT_ID = ""   # report_id тестового квиза (для чистки)


def check(name: str, ok: bool, extra: str = "") -> None:
    results.append((ok, name))
    print(f"{'✅' if ok else '❌'} {name}" + (f" — {extra}" if extra else ""))


def post(path: str, payload: dict, ip: str = IP) -> httpx.Response:
    return httpx.post(
        f"{API}{path}", json=payload,
        headers={"X-Site-Token": TOKEN, "X-Forwarded-For": ip},
        timeout=90,
    )


def get(path: str) -> httpx.Response:
    return httpx.get(
        f"{API}{path}", headers={"X-Site-Token": TOKEN, "X-Forwarded-For": IP},
        timeout=30,
    )


def main() -> None:
    global TOKEN
    env = {}
    env_path = BASE_DIR / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip()
    TOKEN = env.get("SITE_TOKEN", "")

    print(f"=== API: {API} | сайт: {SITE} ===\n")

    # --- 1. health ---
    try:
        r = httpx.get(f"{API}/health", timeout=10)
        h = r.json()
        check("health: сервер жив", r.status_code == 200)
        check("health: LLM настроен", h.get("llm") is True,
              "" if h.get("llm") else "— заполните LLM_API_KEY в backend/.env")
    except Exception as e:  # noqa: BLE001
        check("health: сервер жив", False, f"нет ответа: {e}")
        print("\nСервер не отвечает — запустите: uvicorn app.main:app --port 8000")
        _summary()
        return

    # --- 2. чат-бот ---
    try:
        r = post("/api/chat", {"session_id": SESSION, "message": "Сколько стоит разработка ИИ-агента?"})
        ok = r.status_code == 200 and r.json().get("reply")
        check("чат-бот отвечает", r.status_code == 200 and bool(ok), str(r.status_code))
    except Exception as e:  # noqa: BLE001
        check("чат-бот отвечает", False, str(e))

    # --- 3. квиз (отчёт строится, проверяем ok + report_id) ---
    quiz_payload = {
        "quiz": "efficiency", "email": f"smoke-{STAMP}@aistudio-test.ru", "name": "Smoke Test",
        "score": 6, "maxScore": 10, "pct": 60, "session_id": SESSION,
        "answers": [
            {"question": "Тест", "answer": "Тест", "score": 2},
            {"question": "Тест", "answer": "Тест", "score": 2},
            {"question": "Тест", "answer": "Тест", "score": 2},
        ],
    }
    try:
        r = post("/api/quiz", quiz_payload)
        data = r.json()
        SMOKE_REPORT_ID = data.get("report_id") or ""
        check("квиз принят", r.status_code == 200 and data.get("ok") is True,
              f"report_id={SMOKE_REPORT_ID[:8] or '—'}…")
    except Exception as e:  # noqa: BLE001
        SMOKE_REPORT_ID = ""
        check("квиз принят", False, str(e))

    # --- 4. форма контактов ---
    try:
        r = post("/api/contact", {"name": "Smoke", "email": f"smoke-{STAMP}@aistudio-test.ru"}, ip=IP2)
        check("форма контактов принята", r.status_code == 200 and r.json().get("ok") is True)
    except Exception as e:  # noqa: BLE001
        check("форма контактов принята", False, str(e))

    # --- 5. honeypot ---
    try:
        r = post("/api/contact", {"name": "Bot", "email": f"smoke-{STAMP}@aistudio-test.ru", "website": "http://spam.ru"}, ip=IP3)
        data = r.json()
        check("honeypot отбросил бота", data.get("lead_id") == 0, "lead_id=0 (без сохранения)")
    except Exception as e:  # noqa: BLE001
        check("honeypot отбросил бота", False, str(e))

    # --- 6. rate-limit: 6 заявок с одного IP при норме 5/час ---
    for i in range(6):
        r = post("/api/contact", {"name": "RL", "email": f"smoke-{STAMP}@aistudio-test.ru"}, ip=IP3)
    check("rate-limit ловит шторм (429)", r.status_code == 429, f"последний запрос -> {r.status_code}")

    # --- 7. метрики ---
    try:
        r = get("/api/stats?days=1")
        data = r.json()
        has = all(k in data for k in ("totals", "funnel", "targets"))
        check("метрики /api/stats считаются", r.status_code == 200 and has)
    except Exception as e:  # noqa: BLE001
        check("метрики /api/stats считаются", False, str(e))

    # --- 8. сайт ---
    try:
        pages = ["index.html", "efficiency.html", "security.html", "about.html", "contacts.html", "privacy.html"]
        bad = [p for p in pages if httpx.get(f"{SITE}/{p}", timeout=10).status_code != 200]
        check("сайт: 6 страниц открываются", not bad, ", ".join(bad))
        html = httpx.get(f"{SITE}/index.html", timeout=10).text
        check("сайт: актуальная версия (v=5)", "main.js?v=5" in html, "кэш-бустинг ?v=5")
        check("сайт: favicon подключён", 'assets/favicon.png' in html)
        check("сайт: honeypot в разметке", 'hp-website' in httpx.get(f"{SITE}/contacts.html", timeout=10).text)
    except Exception as e:  # noqa: BLE001
        check("страницы сайта открываются", False, str(e))

    _cleanup()
    _summary()


def _cleanup() -> None:
    """Удаляем всё, что создал этот прогон: лиды, события, файл отчёта."""
    import sqlite3

    conn = sqlite3.connect(BASE_DIR / "data" / "aistudio.db")
    c1 = conn.execute("DELETE FROM leads WHERE session_id=? OR email LIKE 'smoke-%'", (SESSION,)).rowcount
    c2 = conn.execute(
        "DELETE FROM events WHERE session_id=? OR props LIKE ?",
        (SESSION, f"%smoke-{STAMP}%"),
    ).rowcount
    c3 = conn.execute("DELETE FROM chat_messages WHERE session_id=?", (SESSION,)).rowcount
    conn.commit()
    conn.close()

    # сгенерированный отчёт (pdf/html) тоже не нужен
    import glob
    if SMOKE_REPORT_ID:
        for f in glob.glob(str(BASE_DIR / "data" / "reports" / f"{SMOKE_REPORT_ID}.*")):
            Path(f).unlink(missing_ok=True)
            c4_deleted = f
    else:
        c4_deleted = ""
    print(f"\n🧹 Убрано за собой: лидов {c1}, событий {c2}, сообщений чата {c3}" + (f", отчёт {Path(c4_deleted).name}" if c4_deleted else ""))


def _summary() -> None:
    failed = [n for ok, n in results if not ok]
    print()
    if failed:
        print(f"❌ НЕ ПРОШЛО ({len(failed)}):")
        for n in failed:
            print(f"   - {n}")
        sys.exit(1)
    print(f"✅ Все {len(results)} проверок пройдены")


if __name__ == "__main__":
    main()