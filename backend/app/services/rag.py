"""RAG: нарезка баз знаний → эмбеддинги Yandex → локальный векторный индекс → поиск.

Почему свой индекс, а не ChromaDB/torch: корпусов ~30 файлов, сотни
фрагментов — numpy-косинус мгновенен, а эмбеддинги делаем через тот же
API Yandex, что уже настроен (никаких 2 ГБ моделей torch локально).

Индекс: backend/data/rag_index.json. Пересобирается скриптом
scripts/build_rag_index.py (запуск после изменения баз знаний).

Эмбеддинги: пара моделей Yandex — text-search-doc/latest для фрагментов
базы и text-search-query/latest для запросов (они должны совпадать по семейству).
"""
import json
import logging
import math
import re
from pathlib import Path
from typing import Any

import httpx

from ..config import DATA_DIR, settings

log = logging.getLogger("rag")

INDEX_PATH = DATA_DIR / "rag_index.json"
BATCH = 8
MIN_CHUNK = 40          # короче — мусор
MAX_CHUNK = 1800        # длиннее — режем по абзацам

_index: dict[str, Any] | None = None
_docs_vecs: list[list[float]] | None = None


class RagNotReady(Exception):
    pass


# ---------- нарезка ----------

def _split_long(text: str) -> list[str]:
    if len(text) <= MAX_CHUNK:
        return [text]
    parts, buf = [], ""
    for para in text.split("\n\n"):
        if len(buf) + len(para) > MAX_CHUNK and buf:
            parts.append(buf)
            buf = ""
        buf = f"{buf}\n\n{para}".strip()
    if buf:
        parts.append(buf)
    return parts


def chunk_markdown(md: str, source: str) -> list[dict[str, str]]:
    """Фрагменты = разделы ## / ### с накопленной иерархией заголовков."""
    chunks: list[dict[str, str]] = []
    heading: str = ""
    body: list[str] = []

    def flush() -> None:
        text = "\n".join(body).strip()
        if heading or text:
            title = f"{source} — {heading}".strip(" —")
            for part in _split_long(text or heading):
                if len(part) >= MIN_CHUNK:
                    chunks.append({"source": source, "title": title, "text": f"{heading}\n\n{part}".strip()})
        body.clear()

    for line in md.splitlines():
        m = re.match(r"^(#{1,3})\s+(.*)", line)
        if m:
            flush()
            heading = f"{heading[:0]}{m.group(2).strip()}"  # последний заголовок 1-3 уровня
        else:
            body.append(line)
    flush()
    return chunks


# ---------- эмбеддинги (тот же API, что у LLM) ----------

def _folder() -> str:
    """folder_id из LLM_MODEL (gpt://FOLDER/model/latest) или из файла."""
    if settings.llm_model.startswith(("gpt://", "emb://")):
        return settings.llm_model.split("/")[2]
    return ""


def _embed_model(kind: str) -> str:
    explicit = settings.rag_doc_model if kind == "doc" else settings.rag_query_model
    if explicit:
        return explicit
    folder = _folder()
    suffix = "text-search-doc" if kind == "doc" else "text-search-query"
    return f"emb://{folder}/{suffix}/latest"


async def embed_texts(texts: list[str], kind: str = "doc") -> list[list[float]]:
    """Yandex /embeddings принимает ровно одну строку на запрос —
    по запросу на текст, параллелизм ограничен семафором."""
    import asyncio

    url = f"{settings.llm_base_url.rstrip('/')}/embeddings"
    headers = {"Authorization": f"{settings.llm_auth_scheme} {settings.llm_api_key}"}
    model = _embed_model(kind)
    sem = asyncio.Semaphore(3)

    async with httpx.AsyncClient(timeout=60) as client:

        async def one(text: str) -> list[float]:
            async with sem:
                for attempt in range(6):  # 429 → пауза и повтор (бэкофф)
                    resp = await client.post(
                        url, headers=headers, json={"model": model, "input": text[:4000]}
                    )
                    if resp.status_code == 429:
                        await asyncio.sleep(0.6 * (2 ** attempt))
                        continue
                    resp.raise_for_status()
                    return resp.json()["data"][0]["embedding"]
                resp.raise_for_status()
                return []

        return list(await asyncio.gather(*(one(t) for t in texts)))


# ---------- индекс ----------

def load_index() -> dict[str, Any] | None:
    global _index, _docs_vecs
    if _index is None and INDEX_PATH.exists():
        _index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
        _docs_vecs = [c["vec"] for c in _index["chunks"]]
        log.info("RAG-индекс загружен: %s фрагментов", len(_index["chunks"]))
    return _index


def save_index(chunks: list[dict[str, Any]], meta: dict[str, Any]) -> None:
    INDEX_PATH.write_text(
        json.dumps({"meta": meta, "chunks": chunks}, ensure_ascii=False),
        encoding="utf-8",
    )
    global _index, _docs_vecs
    _index = None
    load_index()


def build_index_from_dirs(dirs: list[Path], doc_model: str) -> dict[str, Any]:
    """Синхронный сбор: нарезка + эмбеддинги + сохранение. Вызывается скриптом.
    Эмбеддинги делаются синхронно через httpx sync поверх embed_texts? —
    нет, здесь свой простой цикл, т.к. скрипт — one-shot."""
    import asyncio

    chunks: list[dict[str, str]] = []
    for d in dirs:
        for path in sorted(d.rglob("*.md")):
            rel = str(path.relative_to(d)).replace("\\", "/")
            src = f"{d.name}/{rel}"
            try:
                chunks += chunk_markdown(path.read_text(encoding="utf-8"), src)
            except UnicodeDecodeError:
                log.warning("Пропущен (не UTF-8): %s", path)
    log.info("Нарезано %s фрагментов из %s файлов/каталогов", len(chunks), len(dirs))

    async def do() -> list[list[float]]:
        return await embed_texts([c["text"] for c in chunks], "doc")

    vecs = asyncio.run(do())
    for c, v in zip(chunks, vecs):
        c["vec"] = v
    meta = {"doc_model": doc_model, "count": len(chunks)}
    save_index(chunks, meta)
    return meta


# ---------- поиск ----------

def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    return dot / (na * nb) if na and nb else 0.0


async def search(query: str, k: int | None = None) -> str:
    """Top-k фрагментов для запроса. Возвращает контекст-строку или ''."""
    idx = load_index()
    if not idx or not idx["chunks"]:
        return ""

    qvec = (await embed_texts([query], "query"))[0]
    scored = sorted(
        ((_cosine(qvec, c["vec"]), c) for c in idx["chunks"]),
        key=lambda t: t[0],
        reverse=True,
    )[: k or settings.rag_top_k]

    parts = [
        f"[источник: {c['source']} | {c['title']}]\n{c['text']}"
        for _, c in scored
    ]
    return "\n\n---\n\n".join(parts)