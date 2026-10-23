# AI Studio — лендинг

Сайт-лендинг AI Studio: ИИ-студия для малого и среднего бизнеса (МСП) — аудит эффективности, аудит управления рисками, внедрение ИИ-ассистентов.

## Состав

| Путь | Описание |
|---|---|
| `index.html`, `efficiency.html`, `security.html`, `about.html`, `contacts.html`, `privacy.html` | Страницы сайта (адаптив, тёмная тема: navy `#0D1B2A` + amber `#C8922A`, шрифты Cormorant Garamond + Jost) |
| `css/style.css` | Дизайн-система |
| `js/main.js` | Квиз, навигация, чат-бот, форма контактов; константа `API {base, token}` и `apiPost()` |
| `backend/` | FastAPI-оркестратор (Python 3.12): квиз, контакты, чат-бот с RAG, статистика, email-уведомления, дайджест по расписанию, rate-limit + honeypot |
| `База_знаний_SDaaS/`, `База_знаний_бота_бизнеспроцессов/`, `Chat_bot_knowledge_base/` | Базы знаний ботов (для RAG) |
| `*system_prompt*` | Системные промпты ботов |
| `robots.txt`, `sitemap.xml`, `Assets/favicon.png` | SEO-файлы |

## Backend

Стек: FastAPI + SQLite, docker-compose + Caddy на VPS. LLM — YandexGPT (Yandex AI Studio), эмбеддинг-модель Yandex `text-search-{doc,query}`, векторный индекс — собственный JSON (`backend/data/rag_index.json`, numpy-косинус).

Подробно о деплое — [backend/README.md](backend/README.md).

```bash
cd backend
cp sample.env .env      # вписать ключи (не коммитится)
pip install -r requirements.txt
uvicorn app.main:app --reload

# Пересборка RAG-индекса после правки баз знаний
python -m scripts.build_rag_index

# Проверка всех подсистем
python scripts/smoke_test.py
```

## Интеграции и механики

- Квизы «Аудит эффективности» (5 вопросов) и «Аудит управления рисками» (12 вопросов), A=2/Б=1/В=0 → отчёт PDF-формата в браузере.
- Чат-бот «Антон»: системный промпт + RAG-контекст (топ-4 фрагмента), протокол `<LEAD>` — бот сам собирает лид, кнопки-действия (квиз/переход к форме) прямо в ответах.
- Атрибуция: чат→квиз через `sessionStorage aistudio_chat_sid`, квиз→консультация через `report_id` в CTA.
- Метрики воронки из таблицы `events`: `/api/stats?days=N`; ежедневный дайджест менеджеру по расписанию (`DIGEST_HOUR`, МСК).
- Email-уведомления о горячих лидах через SMTP (Yandex 360 на своём домене). ПДн в зарубежные сервисы не уходят.
- Rate-limit (chat 30/10мин, квиз 10/час, форма 5/час) + honeypot-поле `website`.

## Секреты

`backend/.env` содержит ключи (Yandex API, токен сайта) и **не коммитится** — см. `.gitignore`. Шаблон: `backend/sample.env`.
<img width="800"  alt="Снимок экрана (1549)" src="https://github.com/user-attachments/assets/080df0fa-ad85-417a-a14a-d46620fe73ac" />
<img width="800"  alt="Снимок экрана (1548)" src="https://github.com/user-attachments/assets/7107e07e-b165-4136-808a-3eeb65cca0ee" />
<img width="800" alt="Снимок экрана (1547)" src="https://github.com/user-attachments/assets/b4556e0e-8052-4969-9405-3b6ff2503f52" />
<img width="800"  alt="Снимок экрана (1546)" src="https://github.com/user-attachments/assets/00bc59a3-eb67-40c7-b79e-27288c0e5707" />
<img width="800"  alt="Снимок экрана (1545)" src="https://github.com/user-attachments/assets/0afc413e-44fe-437d-95a6-b25bc3375795" />
<img width="800"  alt="Снимок экрана (1544)" src="https://github.com/user-attachments/assets/79c74189-cab1-48f9-b025-bb8d2d4292ab" />
<img width="800"  alt="Снимок экрана (1543)" src="https://github.com/user-attachments/assets/c1bcfd25-a640-4453-b042-9f4cf9cfd1a4" />
<img width="800"  alt="Снимок экрана (1541)" src="https://github.com/user-attachments/assets/bcbfe5d6-59a8-4c2f-92c1-8f205610ad46" />
<img width="800" alt="Снимок экрана (1540)" src="https://github.com/user-attachments/assets/1bb17435-a760-4693-b870-f93c7fbbe89d" />
<img width="800" alt="Снимок экрана (1539)" src="https://github.com/user-attachments/assets/9814318d-c202-47ef-94f7-a0c07fd81427" />
<img width="800"  alt="Снимок экрана (1538)" src="https://github.com/user-attachments/assets/79608fce-1bbf-40ca-97d7-c4c0f6649d9b" />
<img width="800"  alt="Снимок экрана (1537)" src="https://github.com/user-attachments/assets/64f0b1dc-ef9e-4a37-bf0c-9ec0a9536433" />
<img width="800"  alt="Снимок экрана (1536)" src="https://github.com/user-attachments/assets/443cdc3b-66c2-4b19-a51b-60623b1bee49" />
<img width="800"  alt="Снимок экрана (1535)" src="https://github.com/user-attachments/assets/8e34b3f7-fdef-4eec-9224-5ab41f19052d" />
<img width="800" alt="Снимок экрана (1534)" src="https://github.com/user-attachments/assets/a4ac3090-2716-4919-8a55-d3e49fb8ec41" />
<img width="800" alt="Снимок экрана (1533)" src="https://github.com/user-attachments/assets/f8eb3d1a-43a6-4a6d-944d-8fc100b4c06a" />
<img width="800"  alt="Снимок экрана (1532)" src="https://github.com/user-attachments/assets/cdddcb3c-ba3e-4c5f-962f-89e3ad313420" />
<img width="800"  alt="Снимок экрана (1531)" src="https://github.com/user-attachments/assets/1fb10626-4921-4e80-b542-660636420d71" />
<img width="800" alt="Снимок экрана (1530)" src="https://github.com/user-attachments/assets/e5b7a08d-4b6a-412c-886e-ce574e89033e" />
<img width="800" alt="Снимок экрана (1529)" src="https://github.com/user-attachments/assets/4db07c1c-851b-4008-8e05-1ae20561fce8" />
<img width="800" alt="Снимок экрана (1528)" src="https://github.com/user-attachments/assets/b53c14d3-5cf1-4671-9941-bf7f3bdc19ea" />
<img width="800"  alt="Снимок экрана (1527)" src="https://github.com/user-attachments/assets/9f80565d-743c-4d3e-8a24-b9b321d10557" />
<img width="800"  alt="Снимок экрана (1526)" src="https://github.com/user-attachments/assets/3234121b-95a7-4230-b469-57a27052d2bc" />
<img width="800"  alt="Снимок экрана (1525)" src="https://github.com/user-attachments/assets/eb060b68-3740-49f7-b8ac-3b012f3ca0b9" />
<img width="800"  alt="Снимок экрана (1524)" src="https://github.com/user-attachments/assets/2565fada-60c5-4e57-8b17-0b0215e07813" />
<img width="800"  alt="Снимок экрана (1523)" src="https://github.com/user-attachments/assets/97d34b24-3932-43af-9c19-022e86152084" />
<img width="800" alt="Снимок экрана (1522)" src="https://github.com/user-attachments/assets/8cdf9069-9b93-4302-aff3-fc5b5799e1c7" />
<img width="800" alt="Снимок экрана (1550)" src="https://github.com/user-attachments/assets/29908393-ff16-4958-89bd-fd0319fc0012" />

