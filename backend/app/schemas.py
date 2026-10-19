"""Pydantic-схемы запросов. Зеркалят payload из js/main.js."""
from pydantic import BaseModel, EmailStr, Field, field_validator


class QuizAnswer(BaseModel):
    question: str
    answer: str
    score: int


class QuizSubmission(BaseModel):
    """POST /api/quiz — payload из quizSubmit()."""
    quiz: str = Field(..., pattern="^(efficiency|security)$")
    email: EmailStr
    name: str = ""
    phone: str = ""
    industry: str = ""
    revenue: str = ""
    score: int
    maxScore: int
    pct: int
    answers: list[QuizAnswer]
    session_id: str | None = None   # атрибуция «чат → аудит»
    report_id: str | None = None    # атрибуция «отчёт → консультация»
    website: str = ""               # honeypot: человек не видит поле, бот — заполняет


class ContactSubmission(BaseModel):
    """POST /api/contact — форма contacts.html."""
    name: str
    company: str = ""
    email: EmailStr
    phone: str = ""
    industry: str = ""
    message: str = ""
    source: str | None = None       # utm/параметр ссылки CTA из PDF-отчёта
    website: str = ""               # honeypot: человек не видит поле, бот — заполняет


class ChatRequest(BaseModel):
    """POST /api/chat — виджет чат-бота."""
    session_id: str = Field(..., min_length=8)
    message: str = Field(..., min_length=1, max_length=4000)

    @field_validator("message")
    @classmethod
    def not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("пустое сообщение")
        return v