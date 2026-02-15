"""Промпты бота: загрузка из .md с подстановкой {{placeholder}}."""
from __future__ import annotations

from bot.prompts.agent import AGENT_SYSTEM, MEAL_PARSE, context_message
from bot.prompts.suggest import (
    meals_block,
    suggest_profile_block,
    suggest_stats_block,
    suggest_prompt,
)
from bot.prompts.vision import VISION_SYSTEM, vision_user_text

__all__ = [
    "AGENT_SYSTEM",
    "MEAL_PARSE",
    "context_message",
    "VISION_SYSTEM",
    "vision_user_text",
    "suggest_prompt",
    "suggest_profile_block",
    "suggest_stats_block",
    "meals_block",
]
