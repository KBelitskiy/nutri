"""Промпты для диалогового агента и разбора приёма пищи по тексту (загрузка из .md)."""
from __future__ import annotations

from datetime import datetime

from bot.prompts.loader import load

AGENT_SYSTEM = load("agent/system")
MEAL_PARSE = load("agent/meal_parse")


def context_message(telegram_id: int, *, timezone_name: str = "UTC") -> str:
    """Контекстное сообщение для агента с telegram_id и текущей датой."""
    from zoneinfo import ZoneInfo

    tz = ZoneInfo(timezone_name)
    now = datetime.now(tz=tz).strftime("%Y-%m-%d %H:%M %Z")
    return load("agent/context", telegram_id=telegram_id, now=now)
