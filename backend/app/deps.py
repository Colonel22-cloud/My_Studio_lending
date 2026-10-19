"""Общие зависимости: проверка секретного токена сайта."""
import hmac

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

from .config import settings

_site_token = APIKeyHeader(
    name="X-Site-Token",
    auto_error=False,
    description="Секрет сайта (SITE_TOKEN из backend/.env)",
)


def verify_site_token(x_site_token: str = Security(_site_token)) -> None:
    # bytes: сравнение с не-ASCII строками compare_digest не позволяет
    if not hmac.compare_digest(
        x_site_token.encode("utf-8"), settings.site_token.encode("utf-8")
    ):
        raise HTTPException(status_code=401, detail="Invalid site token")