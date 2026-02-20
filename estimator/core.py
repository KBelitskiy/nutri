"""Ядро оценки КБЖУ: промпты, вызов OpenAI Vision, парсинг ответа."""

from __future__ import annotations

import json
from pathlib import Path

from openai import AsyncOpenAI

_PROMPTS_DIR = Path(__file__).parent / "prompts"


def _load_prompt(name: str, **kwargs: str) -> str:
    text = (_PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")
    for key, value in kwargs.items():
        text = text.replace("{{" + key + "}}", str(value))
    return text.strip()


SYSTEM_PROMPT = _load_prompt("system")


def user_prompt_text(caption: str | None = None) -> str:
    """Собрать текст user-промпта, при наличии подписи — добавить её."""
    base = _load_prompt("user")
    if caption and caption.strip():
        base += "\n\n" + _load_prompt("user_caption", caption=caption.strip())
    return base


def _user_content(image_url: str, caption: str | None) -> list[dict]:
    return [
        {"type": "text", "text": user_prompt_text(caption)},
        {"type": "image_url", "image_url": {"url": image_url}},
    ]


async def analyze_meal_photo(
    client: AsyncOpenAI,
    model: str,
    image_url: str,
    *,
    caption: str | None = None,
) -> dict[str, float | str]:
    """Оценить КБЖУ по фото еды.

    Args:
        client: экземпляр AsyncOpenAI
        model: название модели (например gpt-4o-mini)
        image_url: URL изображения или data URI (base64)
        caption: необязательная подпись к фото от пользователя

    Returns:
        dict с ключами description, calories, protein_g, fat_g, carbs_g
    """
    kwargs: dict = dict(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _user_content(image_url, caption)},
        ],
        temperature=0.0,
    )
    try:
        kwargs["response_format"] = {"type": "json_object"}
        response = await client.chat.completions.create(**kwargs)
    except Exception:
        kwargs.pop("response_format", None)
        response = await client.chat.completions.create(**kwargs)

    content = response.choices[0].message.content or "{}"
    parsed = json.loads(content)
    return {
        "description": str(parsed.get("description", "Блюдо по фото")),
        "calories": float(parsed.get("calories", 0.0)),
        "protein_g": float(parsed.get("protein_g", 0.0)),
        "fat_g": float(parsed.get("fat_g", 0.0)),
        "carbs_g": float(parsed.get("carbs_g", 0.0)),
    }
