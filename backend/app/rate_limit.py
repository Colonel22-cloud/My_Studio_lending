"""Rate-limit для публичных endpoints (защита от спама и злоупотребления API).

In-memory «скользящее окно»: для каждой пары (IP, путь) помним, сколько
запросов пришло за последние N секунд. Порог превышен → 429 Retry-After.

Подходит для одного процесса (наш VPS). Если когда-нибудь будет >
1 инстанса API — переехать на Redis с тем же интерфейсом.

Лимиты подобраны под нормального посетителя без скупости:
  чат        30 сообщений / 10 минут
  квиз       10 отправок / час
  форма      5 отправок / час
  chat/lead  10 отправок / час
"""
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

from .config import settings

# путь → (сколько запросов, окно в секундах)
LIMITS: dict[str, tuple[int, int]] = {
    "/api/chat": (30, 600),
    "/api/chat/lead": (10, 3600),
    "/api/quiz": (10, 3600),
    "/api/contact": (5, 3600),
}

_buckets: dict[tuple[str, str], deque[float]] = defaultdict(deque)
_last_prune = 0.0
_PRUNE_EVERY = 300.0  # подчищать старые записи раз в 5 минут


def _client_ip(request: Request) -> str:
    """За Caddy/nginx реальный IP придёт в X-Forwarded-For."""
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _prune(now: float) -> None:
    global _last_prune
    if now - _last_prune < _PRUNE_EVERY:
        return
    for key in list(_buckets):
        limit, window = LIMITS.get(key[1], (0, _PRUNE_EVERY * 2))
        if len(_buckets[key]) > limit:
            cut = now - window - 1
            while _buckets[key] and _buckets[key][0] <= cut:
                _buckets[key].popleft()
            if not _buckets[key]:
                del _buckets[key]
    _last_prune = now


def check_rate_limit(request: Request) -> None:
    """FastAPI-зависимость: вешается на публичные POST-роуты."""
    if not settings.rate_limit_enabled:
        return

    path = request.url.path
    rule = LIMITS.get(path)
    if not rule:
        return
    limit, window = rule

    now = time.monotonic()
    _prune(now)

    key = (_client_ip(request), path)
    dq = _buckets[key]
    while dq and dq[0] <= now - window:
        dq.popleft()
    if len(dq) >= limit:
        retry = max(1, int(window - (now - dq[0])))
        raise HTTPException(
            status_code=429,
            detail="Слишком много запросов. Попробуйте позже.",
            headers={"Retry-After": str(retry)},
        )
    dq.append(now)