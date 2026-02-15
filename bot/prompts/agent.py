"""Промпты для диалогового агента и разбора приёма пищи по тексту (загрузка из .md)."""
from __future__ import annotations

from bot.prompts.loader import load

# Полные тексты для LLM — загружаются из agent/*.md
AGENT_SYSTEM = load("agent/system")
MEAL_PARSE = load("agent/meal_parse")


def context_message(telegram_id: int) -> str:
    """Контекстное сообщение для агента с telegram_id (из agent/context.md)."""
    return load("agent/context", telegram_id=telegram_id)
