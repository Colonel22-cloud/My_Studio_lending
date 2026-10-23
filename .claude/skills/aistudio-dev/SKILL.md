---
name: aistudio-dev
description: Рабочий процесс для репозитория AI Studio (лендинг + FastAPI бэкенд). Используй при запуске сайта/API, вносении изменений в страницы и бэкенд, обновлении README, проверке ошибок (smoke-test, синтаксис, CORS/token) и подготовке проекта к публикации.
---

# AI Studio — работа с репозиторием

Сайт-лендинг (статика: HTML/CSS/JS) + FastAPI-оркестратор. Все команды ниже
проверены в этом репозитории; пути указаны от корня, если не сказано иное.

## 1. Структура (что где лежит)

| Путь | Что это |
|---|---|
| `index.html`, `efficiency.html`, `security.html`, `about.html`, `contacts.html`, `privacy.html` | Страницы лендинга (тёмная тема: navy `#0D1B2A` + amber `#C8922A`; шрифты Cormorant Garamond + Jost) |
| `css/style.css` | Вся дизайн-система (один файл) |
| `js/main.js` | Весь клиентский JS: квиз, форма контактов, чат-бот, навигация. В начале файла — `const API {base, token}` и `apiPost()` |
| `backend/app/` | FastAPI: `main.py` (app, CORS), `config.py` (.env), `db.py` (SQLite), `schemas.py`, `deps.py` (проверка X-Site-Token), `rate_limit.py` |
| `backend/app/routers/` | `quiz.py` (POST /api/quiz), `contact.py`, `chat.py` (RAG-чат + лид), `stats.py` |
| `backend/app/services/` | `llm.py` (YandexGPT по OpenAI-совместимому API), `rag.py`, `emailer.py`, `report.py` (квиз → LLM → отчёт) |
| `backend/scripts/smoke_test.py` | Полный смоук-тест API + сайта |
| `backend/scripts/build_rag_index.py` | Пересборка RAG-индекса |
| `База_знаний_SDaaS/`, `База_знаний_бота_бизнеспроцессов/`, `Chat_bot_knowledge_base/` | Базы знаний для RAG |
| `Site_architecture.txt` | Исходные тексты страниц (черновик, откуда растут HTML) |
| `backend/.env`, `backend/data/` | Секреты и данные — **вне git, не коммитить** |

## 2. Запуск сервиса

Два фоновых процесса (Bash с `run_in_background: true`):

```bash
# 1. API — порт 8000. НЕ использовать --reload: на этой машине заканчивается память.
cd backend && python -m uvicorn app.main:app --port 8000

# 2. Статика — порт 5500 (совпадает с ALLOWED_ORIGINS в backend/.env)
python -m http.server 5500
```

Проверка готовности:

```bash
curl -s http://127.0.0.1:8000/health   # {"status":"ok","llm":true,"smtp":...}
curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:5500/index.html
```

`smtp:false` — норма локально: письма логируются в консоль бэкенда
(подробности в ответах бэкенда: «SMTP не настроен, письмо … не отправлено») —
это не ошибка, если не тестировали почту.

## 3. Внесение изменений

- Правки вёрстки/текстов: только соответствующая `.html` + при необходимости
  `css/style.css`. Не создавать дополнительные css/js-файлы — вся логика в
  `js/main.js`, стили в `css/style.css`.
- Новый текст для страниц согласовывать со стилем из `Site_architecture.txt`.
- Правки баз знаний → после них **обязательно** пересобрать индекс:
  `cd backend && python -m scripts.build_rag_index`
- Изменения в payload квиза/формы `js/main.js` должны зеркально меняться в
  `backend/app/schemas.py` — это парные правки, всегда делать вместе.
- Критичная связка: `SITE_TOKEN` из `backend/.env` должен совпадать с
  `API.token` в `js/main.js:15`. Меняешь одно — меняй и другое, иначе все
  запросы вернут 403.

## 4. Обновление README

- Корневой `README.md` — обзор проекта, таблица «Состав», краткий запуск.
- `backend/README.md` — структура бэкенда, переменные `.env` (описание каждого
  ключа из `backend/sample.env`), деплой на VPS (docker-compose + Caddy).
- При добавлении нового роутера/серванса/скрипта добавлять его в оба README в
  существующем табличном/древовидном формате, не переписывать целиком.
- README ведутся по-русски; тон — краткий и практичный, без маркетинга.

## 5. Проверка ошибок

Порядок после изменений:

```bash
# синтаксис Python
cd backend && python -m py_compile app/main.py app/schemas.py
# и т.п. для каждого тронутого файла

# полный конвейер (серверы должны быть запущены, см. п.2)
cd backend && python scripts/smoke_test.py
```

`smoke_test.py` проверяет: health, чат-бот, квиз, форму, honeypot,
rate-limit, метрики, доступность страниц сайта; свои лиды удаляет сам.
Дополнительные проверки вручную:

- CORS: фронт обращается с `http://localhost:5500` — домен должен быть в
  `ALLOWED_ORIGINS` (`backend/.env`), иначе запросы отбивает браузер.
- `GET /api/stats` — после правок квиза счётчики не должны дублироваться.
- Логи бэкенда: фоновый Bash-процесс из п.2 — читать его output-файл
  (`tail`) при каждой жалобе пользователя на форму/чат/отчёт.

## 6. Подготовка к публикации

Чек-лист перед коммитом/деплоем:

1. `git status` — в коммит не попали: `backend/.env`, `backend/data/*`,
   `shots/*` (скриншоты). Если попали — убрать из коммита и добавить в
   `.gitignore`.
2. `ALLOWED_ORIGINS` в `backend/.env` — добавить боевой домен рядом с
   `localhost:5500`.
3. `API.base` в `js/main.js:13` — на проде указать https-домен API.
4. Токен: если менялся `SITE_TOKEN`, обновить и `js/main.js`, и коммит
   деплоя бэкенда **синхронно**.
5. `robots.txt` и `sitemap.xml` — актуальны (домен, новые страницы).
6. Смок-тест зелёный (п.5), затем коммит и пуш в `origin/main`.