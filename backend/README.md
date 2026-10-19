# AI Studio API — бэкенд

FastAPI: аудиторы квизов (отчёт PDF → email), чат-бот квалификации лидов,
лог событий воронки и метрики.

## Структура

```
backend/
├── app/
│   ├── main.py            # FastAPI app, CORS, роутеры
│   ├── config.py          # настройки из .env
│   ├── db.py              # SQLite: events / leads / chat_messages
│   ├── schemas.py         # pydantic-схемы (зеркалят payload из js/main.js)
│   ├── deps.py            # проверка X-Site-Token
│   ├── routers/
│   │   ├── quiz.py        # POST /api/quiz
│   │   ├── contact.py     # POST /api/contact
│   │   ├── chat.py        # POST /api/chat, POST /api/chat/lead
│   │   └── stats.py       # GET  /api/stats
│   ├── services/
│   │   ├── llm.py         # OpenAI-совместимый клиент (YandexGPT/GigaChat)
│   │   ├── emailer.py     # SMTP-отправка (Yandex 360 / Mail.ru)
│   │   └── report.py      # ответы квиза → LLM → MD → HTML → PDF
│   └── templates/report.html  # брендированный PDF-шаблон
├── data/                  # SQLite + PDF-отчёты (вне git)
└── requirements.txt
```

## Локальный запуск

```bash
cd backend
pip install -r requirements.txt     # WeasyPrint на Windows потребует GTK — на VPS проще
cp sample.env .env                  # заполнить SITE_TOKEN и LLM-ключи
uvicorn app.main:app --reload --port 8000
```

Docs: http://localhost:8000/docs · Health: http://localhost:8000/health

Пока LLM/SMTP не настроены, API работает в деградированном режиме:
квизы и лиды сохраняются в БД, отчёты и письма логируются
(`report_failed` / warning в логах) — этого достаточно для отладки фронта.

## Деплой на VPS (этап 0)

```bash
# 1. Ubuntu 22.04+, useradd, docker + docker compose plugin
# 2. backend/Dockerfile + docker-compose.yml (см. ниже)
# 3. Caddy как реверс-прокси: HTTPS автоматически по доменному имени
```

`docker-compose.yml` (положить в backend/):

```yaml
services:
  api:
    build: .
    restart: unless-stopped
    env_file: .env
    volumes:
      - ./data:/app/data
    expose: ["8000"]
  caddy:
    image: caddy:2-alpine
    restart: unless-stopped
    ports: ["80:80", "443:443"]
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile
      - caddy_data:/data
    depends_on: [api]
volumes: { caddy_data: {} }
```

`Caddyfile`:

```
api.ваш-домен.ru {
    reverse_proxy api:8000
}
```

`Dockerfile`:

```dockerfile
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 libpangoft2-1.0-0 libcairo2 fonts-dejavu && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## Шрифты для PDF (после покупки домена)

В `app/templates/report.html` указаныfallback-шрифты: DejaVu (кириллица OK).
Для брендированного вида положить TTF Cormorant Garamond и Jost в
`app/templates/fonts/` и добавить в шаблон `@font-face`.

## Смоук-тест (проверка всего за 1 команду)

```
cd backend
python scripts/smoke_test.py
```

12 проверок: health, чат-бот, квиз (реальный прогон LLM и отчёта), форма,
honeypot, rate-limit, метрики, страницы сайта. Тест убирает за собой —
метрики остаются чистыми. Сервер и Live Server должны быть запущены.

## SEO

- `robots.txt` + `sitemap.xml` (в корне сайта) — после регистрации домена
  заменить «ваш-домен.ru» в обоих файлах
- `assets/favicon.png` — favicon всех страниц
- OpenGraph-теги в <head> каждой страницы (карточка сайта в мессенджерах);
  заготовка Яндекс.Метрики — закомментирована в конце страниц, включить
  после домена (вписать ID счётчика)

## LLM-модели (экономика)

- `LLM_MODEL` — большая модель: **отчёты квиз-аудиторов** (качество текста)
- `CHAT_LLM_MODEL` — лёгкая `yandexgpt-lite`: **чат-бот** (в разы дешевле);
  пусто = использовать LLM_MODEL

## Метрики

`GET /api/stats?days=7` — воронка против целевых значений:

| Метрика | Источник |
|---|---|
| Диалогов в день | events(chat_reply, distinct session_id) |
| Доля диалогов со сбором контактов | leads(source=chat) / диалоги |
| Контакты → аудит | leads(source=quiz, session_id не NULL) / leads(source=chat) |
| Аудит → консультация | events(lead_captured, intent=consultation) / leads(source=quiz) |
| Среднее/p95 время ответа | events(chat_reply, response_ms) |

Позже: Grafana поверх той же БД (cron-дайджест уже реализован).

## Ежедневный дайджест

Сервер сам раз в день (в `DIGEST_HOUR` по МСК, по умолчанию 9:05) отправляет
на `MANAGER_EMAIL` письмо: за сутки — диалоги, лиды, квизы, конверсии воронки
против целевых значений, среднее/p95 время ответа; плюс тренд за 7 дней.

- Расчёт метрик: `app/services/metrics.py` (одна точка правды для /api/stats и дайджеста)
- Сборка письма и планировщик: `app/services/digest.py`
- Пока SMTP не настроено — текст дайджеста печатается в лог сервера раз в сутки

## Развитие (следующие этапы)

- Этап 3: RAG — чанкинг баз знаний (../База_знаний_*), эмбеддинги bge-m3,
  ChromaDB, подстановка контекста в chat.py перед вызовом LLM.
- Автообновление access-токена GigaChat, если выберем Сбер вместо Yandex
  (сейчас llm.py умеет статический ключ: `Api-Key` — Yandex, `Bearer` — IAM-токен).
- Этап 7: модуль crm.py — вебхooks Битрикс24 как второй канал лидов.

## Защита от спама (этап 9, реализовано)

1. **Rate-limit** — `app/rate_limit.py`, in-memory скользящее окно по (IP, путь):
   чат 30/10 мин, квиз 10/час, форма 5/час, chat/lead 10/час. Превышение → 429
   со `Retry-After`. Отключается `RATE_LIMIT_ENABLED=false` в .env.
   При одном инстансе API достаточно; при горизонтальном масштабировании —
   переезд на Redis (тот же интерфейс check_rate_limit).
2. **Honeypot** — невидимое поле `website` в форме контактов и в шаге email
   квиза (css `.hp-field`). Боты автозаполняют его → заявка молча отбрасывается
   (бот получает «ok», лид не создаётся, пишется событие `spam_blocked`).
3. **Ограничения схемы** — max_length сообщения чата (4000), валидация email
   (EmailStr), паттерн quiz.