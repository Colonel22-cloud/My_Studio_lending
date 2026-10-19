"""Конфигурация приложения (читает .env в каталоге backend/)."""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent  # backend/


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- API ---
    allowed_origins: list[str] = ["*"]
    site_token: str = "change_me"

    # --- Email ---
    smtp_host: str = ""
    smtp_port: int = 465
    smtp_user: str = ""
    smtp_password: str = ""
    email_from: str = ""
    manager_email: str = ""

    # --- LLM ---
    llm_base_url: str = ""
    llm_api_key: str = ""
    # Yandex AI Studio: "Api-Key" (API-ключ) или "Bearer" (IAM-токен);
    # GigaChat: "Bearer" (access-токен)
    llm_auth_scheme: str = "Api-Key"
    llm_model: str = "yandexgpt"
    # Модель для чат-бота (обычно дешевле/легче основной).
    # Пусто = та же, что и основная (LLM_MODEL). Пример: gpt://<folder>/yandexgpt-lite/latest
    chat_llm_model: str = ""
    llm_temperature: float = 0.4
    llm_timeout: float = 120.0

    # --- Пути ---
    prompts_dir: Path = BASE_DIR.parent
    knowledge_dir: Path = BASE_DIR.parent
    report_template: Path = BASE_DIR / "app" / "templates" / "report.html"

    # --- RAG ---
    rag_top_k: int = 4
    # Пусто = derived из LLM_MODEL: emb://<folder>/text-search-{doc|query}/latest
    rag_doc_model: str = ""
    rag_query_model: str = ""

    # --- Дайджест (ежедневное письмо менеджеру) ---
    digest_hour: int = 9  # во сколько по МСК отправлять (письмо уйдёт в XX:05)

    # --- Защита от спама ---
    rate_limit_enabled: bool = True  # RATE_LIMIT_ENABLED=false — отключить (для тестов)

    # --- БД ---
    db_url: str = f"sqlite:///{BASE_DIR / 'data' / 'aistudio.db'}"

    @property
    def llm_configured(self) -> bool:
        return bool(self.llm_base_url and self.llm_api_key)

    @property
    def smtp_configured(self) -> bool:
        return bool(self.smtp_host and self.smtp_user and self.smtp_password)


settings = Settings()

DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)