"""Конвейер отчёта: ответы квиза → LLM → Markdown → брендированный HTML → PDF.

Промпты аудиторов берутся из корня проекта:
  efficiency → Business_automation_bot_system_prompt.md
  security   → DSaaS_Bot_System_prompt.md
"""
from datetime import datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

from ..config import settings
from . import llm

QUIZ_PROMPTS = {
    "efficiency": "Business_automation_bot_system_prompt.md",
    "security": "DSaaS_Bot_System_prompt.md",
}

TITLES = {
    "efficiency": "ЭКСПРЕСС-ОЦЕНКА ОПЕРАЦИОННОЙ ЭФФЕКТИВНОСТИ И ПОТЕНЦИАЛА ИИ-АВТОМАТИЗАЦИИ",
    "security": "ЭКСПРЕСС-ОЦЕНКА ЗРЕЛОСТИ УПРАВЛЕНИЯ РИСКАМИ БИЗНЕСА",
}

REPORTS_DIR = Path("data/reports")
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def format_answers(quiz_type: str, data: dict[str, Any]) -> str:
    """Готовит текст запроса к аудитору из ответов квиза."""
    answers = "\n".join(
        f"{i+1}. {a['question']}\n   Ответ: {a['answer']} (баллов: {a['score']})"
        for i, a in enumerate(data["answers"])
    )
    optional = "\n".join(
        f"- {k}: {v}"
        for k, v in (
            ("Сфера деятельности", data.get("industry")),
            ("Годовой оборот", data.get("revenue")),
            ("Имя", data.get("name")),
        )
        if v
    )
    return (
        f"Тип аудита: {TITLES[quiz_type]}\n"
        f"Итоговый балл: {data['score']} из {data['maxScore']} "
        f"({data['pct']}% от максимума)\n"
        f"{f'Данные клиента:\n{optional}\n' if optional else ''}"
        f"Ответы на вопросы:\n{answers}\n\n"
        "Сформируй отчёт строго по структуре из системного промпта."
    )


async def generate_report_markdown(quiz_type: str, data: dict[str, Any]) -> str:
    """Вызывает аудитора, возвращает отчёт в Markdown."""
    system = llm.load_prompt(QUIZ_PROMPTS[quiz_type])
    return await llm.chat_complete(
        system=system,
        user=format_answers(quiz_type, data),
        max_tokens=6000,
        temperature=0.3,  # отчёт — фактура, не творчество
    )


def markdown_to_html(md: str) -> str:
    import markdown as md_lib

    return md_lib.markdown(
        md, extensions=["tables", "sane_lists", "smarty"],
        output_format="html5",
    )


def render_html(quiz_type: str, report_html: str, meta: dict[str, Any]) -> str:
    env = Environment(
        loader=FileSystemLoader(settings.report_template.parent),
        autoescape=False,
    )
    tpl = env.get_template(settings.report_template.name)
    return tpl.render(
        title=TITLES[quiz_type],
        body=report_html,
        date=datetime.now().strftime("%d.%m.%Y"),
        **meta,
    )


def html_to_pdf(html: str, out_path: Path) -> Path:
    """Мы делаем PDF через WeasyPrint (на VPS). Если движок недоступен
    (локальная Windows без GTK) — сохраняем отчёт как HTML, конвейер
    не ломается."""
    try:
        from weasyprint import HTML  # lazy: ему нужны системные библиотеки
    except (ImportError, OSError):
        out = out_path.with_suffix(".html")
        out.write_text(html, encoding="utf-8")
        return out

    HTML(string=html, base_url=".").write_pdf(str(out_path))
    return out_path


async def build_and_save_pdf(
    quiz_type: str,
    data: dict[str, Any],
    report_id: str,
) -> Path:
    md = await generate_report_markdown(quiz_type, data)
    html = render_html(quiz_type, markdown_to_html(md), meta={
        "client_name": data.get("name") or "",
        "client_email": data.get("email", ""),
        "report_id": report_id,
        "video_demo_url": settings.video_demo_url,
    })
    out = REPORTS_DIR / f"{report_id}.pdf"
    return html_to_pdf(html, out)