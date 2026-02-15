from __future__ import annotations

from bot.database.models import MealLog, User
from bot.services.nutrition import summarize_progress


def parse_float(value: str) -> float | None:
    try:
        return float(value.replace(",", ".").strip())
    except ValueError:
        return None


def parse_int(value: str) -> int | None:
    try:
        return int(value.strip())
    except ValueError:
        return None


def user_targets(user: User) -> dict[str, float]:
    return {
        "daily_calories_target": user.daily_calories_target,
        "daily_protein_target": user.daily_protein_target,
        "daily_fat_target": user.daily_fat_target,
        "daily_carbs_target": user.daily_carbs_target,
    }


def progress_text(consumed: dict[str, float], user: User) -> str:
    targets = user_targets(user)
    p = summarize_progress(consumed, targets)
    return (
        f"Сегодня: {consumed['calories']:.1f}/{targets['daily_calories_target']:.1f} ккал "
        f"({p['calories_pct']}%), осталось {p['calories_left']:.1f} ккал.\n"
        f"Б: {consumed['protein_g']:.1f}/{targets['daily_protein_target']:.1f} г "
        f"({p['protein_pct']}%), осталось {p['protein_left']:.1f} г\n"
        f"Ж: {consumed['fat_g']:.1f}/{targets['daily_fat_target']:.1f} г "
        f"({p['fat_pct']}%), осталось {p['fat_left']:.1f} г\n"
        f"У: {consumed['carbs_g']:.1f}/{targets['daily_carbs_target']:.1f} г "
        f"({p['carbs_pct']}%), осталось {p['carbs_left']:.1f} г"
    )


def today_with_meals_text(meals: list[MealLog], consumed: dict[str, float], user: User) -> str:
    """Сводка за сегодня: список приёмов пищи с калориями + итог по КБЖУ."""
    lines = ["Приёмы пищи за сегодня:"]
    if meals:
        for m in meals:
            lines.append(f"  • {m.description} — {m.calories:.0f} ккал")
        lines.append("")
    lines.append(progress_text(consumed, user))
    return "\n".join(lines)

