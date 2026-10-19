"""AI Studio API — FastAPI app.

Запуск локально (из каталога backend/):
  pip install -r requirements.txt
  cp sample.env .env   # затем заполнить ключи
  uvicorn app.main:app --port 8000

Docs: http://localhost:8000/docs
"""
import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .routers import chat, contact, quiz, stats
from .services.digest import scheduler_loop

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Фоновые задачи приложения (запуск/остановка вместе с сервером)."""
    task = asyncio.create_task(scheduler_loop())
    yield
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task


app = FastAPI(
    title="AI Studio API",
    version="0.2.0",
    description="Квизы-аудиторы, чат-бот квалификации лидов, метрики воронки",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_methods=["POST", "GET"],
    allow_headers=["Content-Type", "X-Site-Token"],
)

app.include_router(quiz.router)
app.include_router(contact.router)
app.include_router(chat.router)
app.include_router(stats.router)


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "llm": settings.llm_configured,
        "smtp": settings.smtp_configured,
        "digest_hour": settings.digest_hour,
    }