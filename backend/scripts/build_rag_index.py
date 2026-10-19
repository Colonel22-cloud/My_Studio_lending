"""Сборка RAG-индекса по базам знаний проекта.

Запуск (из backend/):  python -m scripts.build_rag_index
Повторять после изменения файлов баз знаний.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings  # noqa: E402
from app.services import rag  # noqa: E402

DEFAULT_DIRS = [
    "База_знаний_SDaaS",
    "База_знаний_бота_бизнеспроцессов",
    "Chat_bot_knowledge_base",
]


def main() -> None:
    if not settings.llm_configured:
        sys.exit("LLM не настроен в .env — нужны LLM_BASE_URL и LLM_API_KEY")
    root = Path(settings.knowledge_dir)
    dirs = [root / name for name in DEFAULT_DIRS]
    for d in dirs:
        if not d.exists():
            sys.exit(f"Нет каталога базы знаний: {d}")

    doc_model = rag._embed_model("doc")
    print(f"Эмбеддинги через: {doc_model}")
    meta = rag.build_index_from_dirs(dirs, doc_model)
    print(f"Готово: {meta['count']} фрагментов, индекс в {rag.INDEX_PATH}")


if __name__ == "__main__":
    main()