from __future__ import annotations

import json

from openai import AsyncOpenAI


VISION_PROMPT = """
Ты нутрициолог. Оцени блюдо по фото.
Если пользователь прислал подпись к фото (граммовки, состав, название блюда) — обязательно учти её для более точной оценки порции и КБЖУ.
Верни строго JSON-объект с полями:
description (string), calories (number), protein_g (number), fat_g (number), carbs_g (number).
Без markdown и без дополнительных комментариев.
"""


def _user_content(image_url: str, caption: str | None) -> list[dict]:
    text = "Оцени КБЖУ блюда по фото."
    if caption and caption.strip():
        text += f"\n\nПодпись пользователя к фото: {caption.strip()}"
    return [
        {"type": "text", "text": text},
        {"type": "image_url", "image_url": {"url": image_url}},
    ]


async def analyze_meal_photo(
    client: AsyncOpenAI, model: str, image_url: str, *, caption: str | None = None
) -> dict[str, float | str]:
    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": VISION_PROMPT},
            {
                "role": "user",
                "content": _user_content(image_url, caption),
            },
        ],
        temperature=0.2,
    )
    content = response.choices[0].message.content or "{}"
    parsed = json.loads(content)
    return {
        "description": str(parsed.get("description", "Блюдо по фото")),
        "calories": float(parsed.get("calories", 0.0)),
        "protein_g": float(parsed.get("protein_g", 0.0)),
        "fat_g": float(parsed.get("fat_g", 0.0)),
        "carbs_g": float(parsed.get("carbs_g", 0.0)),
    }

