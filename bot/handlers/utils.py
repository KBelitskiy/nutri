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


def _bar(pct: float, width: int = 12) -> str:
    bounded = max(0.0, min(100.0, pct))
    filled = min(width, int((bounded / 100.0) * width))
    return "█" * filled + "░" * (width - filled)


def progress_text(consumed: dict[str, float], user: User) -> str:
    targets = user_targets(user)
    p = summarize_progress(consumed, targets)
    return (
        f"Калории: {_bar(p['calories_pct'])} {p['calories_pct']:.1f}% "
        f"({consumed['calories']:.1f}/{targets['daily_calories_target']:.1f}), "
        f"осталось {p['calories_left']:.1f}\n"
        f"Белок:   {_bar(p['protein_pct'])} {p['protein_pct']:.1f}% "
        f"({consumed['protein_g']:.1f}/{targets['daily_protein_target']:.1f} г), "
        f"осталось {p['protein_left']:.1f} г\n"
        f"Жиры:    {_bar(p['fat_pct'])} {p['fat_pct']:.1f}% "
        f"({consumed['fat_g']:.1f}/{targets['daily_fat_target']:.1f} г), "
        f"осталось {p['fat_left']:.1f} г\n"
        f"Углеводы:{_bar(p['carbs_pct'])} {p['carbs_pct']:.1f}% "
        f"({consumed['carbs_g']:.1f}/{targets['daily_carbs_target']:.1f} г), "
        f"осталось {p['carbs_left']:.1f} г"
    )


def today_with_meals_text(
    meals: list[MealLog],
    consumed: dict[str, float],
    user: User,
    *,
    water_today_ml: int | None = None,
    streak_days: int | None = None,
) -> str:
    """Сводка за сегодня: список приёмов пищи с калориями + итог по КБЖУ."""
    lines = ["Приёмы пищи за сегодня:"]
    if meals:
        for m in meals:
            lines.append(f"  • {m.description} — {m.calories:.0f} ккал")
        lines.append("")
    lines.append(progress_text(consumed, user))
    if water_today_ml is not None:
        target_ml = int(user.daily_water_target_ml or max(1200, int(float(user.weight_start_kg) * 30)))
        water_pct = round((water_today_ml / target_ml * 100.0), 1) if target_ml > 0 else 0.0
        lines.append("")
        lines.append(
            f"Вода: {water_today_ml}/{target_ml} мл ({water_pct}%), "
            f"ост. {max(0, target_ml - water_today_ml)} мл"
        )
    if streak_days is not None:
        lines.append(f"Стрик по калориям: {streak_days} дн.")
    return "\n".join(lines)

