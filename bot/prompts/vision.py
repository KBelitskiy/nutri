"""Промпты для анализа приёма пищи по фото (загрузка из .md)."""
from __future__ import annotations

from bot.prompts.loader import load

# Полный системный промпт для vision — из vision/system.md
VISION_SYSTEM = load("vision/system")


def vision_user_text(caption: str | None = None) -> str:
    """Текст запроса к vision: из vision/user.md, при наличии подписи добавляется vision/user_caption.md."""
    base = load("vision/user")
    if caption and caption.strip():
        return base + "\n\n" + load("vision/user_caption", caption=caption.strip())
    return base
