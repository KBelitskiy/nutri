from __future__ import annotations

import json

from openai import AsyncOpenAI

from bot.prompts import VISION_SYSTEM, vision_user_text


def _user_content(image_url: str, caption: str | None) -> list[dict]:
    return [
        {"type": "text", "text": vision_user_text(caption)},
        {"type": "image_url", "image_url": {"url": image_url}},
    ]


async def analyze_meal_photo(
    client: AsyncOpenAI, model: str, image_url: str, *, caption: str | None = None
) -> dict[str, float | str]:
    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": VISION_SYSTEM},
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

