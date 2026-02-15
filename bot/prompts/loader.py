"""Загрузка промптов из .md файлов с подстановкой {{placeholder}}."""
from __future__ import annotations

from pathlib import Path

_PROMPTS_DIR = Path(__file__).parent


def load(name: str, **kwargs: str | int | float) -> str:
    """
    Читает файл bot/prompts/{name}.md (name может содержать /, например agent/system)
    и подставляет {{key}} из kwargs. Возвращает текст с подставленными значениями (strip).
    """
    path = _PROMPTS_DIR / (name + ".md")
    text = path.read_text(encoding="utf-8")
    for key, value in kwargs.items():
        text = text.replace("{{" + key + "}}", str(value))
    return text.strip()
