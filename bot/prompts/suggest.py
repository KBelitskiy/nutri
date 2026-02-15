"""Промпты для сценария «Рекомендации» (загрузка из .md, параметризация блоков)."""
from __future__ import annotations

from bot.prompts.loader import load


def suggest_profile_block(
    gender: str,
    age: int,
    height_cm: float,
    weight_start_kg: float,
    activity_level: str,
    goal: str,
    daily_calories_target: float,
    daily_protein_target: float,
    daily_fat_target: float,
    daily_carbs_target: float,
) -> str:
    """Блок «Профиль пользователя» из suggest/profile_block.md."""
    return load(
        "suggest/profile_block",
        gender=gender,
        age=age,
        height_cm=f"{height_cm:.0f}",
        weight_start_kg=f"{weight_start_kg:.0f}",
        activity_level=activity_level,
        goal=goal,
        daily_calories_target=f"{daily_calories_target:.0f}",
        daily_protein_target=f"{daily_protein_target:.0f}",
        daily_fat_target=f"{daily_fat_target:.0f}",
        daily_carbs_target=f"{daily_carbs_target:.0f}",
    )


def suggest_stats_block(
    consumed_calories: float,
    consumed_protein: float,
    consumed_fat: float,
    consumed_carbs: float,
    calories_left: float,
    protein_left: float,
    fat_left: float,
    carbs_left: float,
) -> str:
    """Блок «Потребление за сегодня» из suggest/stats_block.md."""
    return load(
        "suggest/stats_block",
        consumed_calories=f"{consumed_calories:.0f}",
        consumed_protein=f"{consumed_protein:.0f}",
        consumed_fat=f"{consumed_fat:.0f}",
        consumed_carbs=f"{consumed_carbs:.0f}",
        calories_left=f"{calories_left:.0f}",
        protein_left=f"{protein_left:.0f}",
        fat_left=f"{fat_left:.0f}",
        carbs_left=f"{carbs_left:.0f}",
    )


def meals_block(meals_lines: list[str]) -> str:
    """Блок «Приёмы пищи за сегодня» из suggest/meals_block.md ({{content}})."""
    if not meals_lines:
        content = "Приёмов пищи за сегодня пока нет."
    else:
        content = "Приёмы пищи за сегодня:\n" + "\n".join(meals_lines)
    return load("suggest/meals_block", content=content)


def suggest_prompt(
    profile_block: str,
    stats_block: str,
    meals_block: str,
) -> str:
    """Полный промпт рекомендаций из suggest/prompt.md с подстановкой блоков."""
    return load(
        "suggest/prompt",
        profile_block=profile_block,
        stats_block=stats_block,
        meals_block=meals_block,
    )
