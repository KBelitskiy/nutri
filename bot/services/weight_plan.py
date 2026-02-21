from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Literal

from bot.services.nutrition import ACTIVITY_MULTIPLIERS, calculate_bmr

Mode = Literal["light", "medium", "hard"]
GoalDirection = Literal["lose", "gain", "maintain"]
Gender = Literal["male", "female"]
ActivityLevel = Literal["low", "light", "moderate", "high", "very_high"]

LOSE_DEFICIT_KCAL: dict[Mode, float] = {"light": 300.0, "medium": 500.0, "hard": 750.0}
GAIN_SURPLUS_KCAL: dict[Mode, float] = {"light": 200.0, "medium": 350.0, "hard": 500.0}
MIN_CALORIES: dict[Gender, float] = {"female": 1200.0, "male": 1500.0}

# 5 лет — достаточно даже для лайт-режима при большой разнице в весе
_MAX_FORECAST_WEEKS = 560


def _resolve_direction(current_weight: float, target_weight: float) -> GoalDirection:
    if abs(target_weight - current_weight) < 0.01:
        return "maintain"
    return "lose" if target_weight < current_weight else "gain"


def _base_delta_kcal(direction: GoalDirection, mode: Mode) -> float:
    if direction == "lose":
        return -LOSE_DEFICIT_KCAL[mode]
    if direction == "gain":
        return GAIN_SURPLUS_KCAL[mode]
    return 0.0


def _calorie_floor(gender: str) -> float:
    return MIN_CALORIES["female"] if gender == "female" else MIN_CALORIES["male"]


def build_weight_forecast(
    current_weight: float,
    target_weight: float,
    gender: str,
    age: int,
    height_cm: float,
    activity_level: str,
    mode: str,
) -> list[dict]:
    """
    Понедельный прогноз веса.

    Модель:
    - Дефицит/профицит поддерживается фиксированным (питание корректируется под новый TDEE).
    - BMR пересчитывается каждую неделю по текущему весу (снижение метаболизма).
    - После 8 недель применяется адаптивный термогенез: эффективный TDEE снижается
      до −5% от расчётного, что немного уменьшает реальный дефицит.
    - Минимальный калораж: 1200 ккал (ж) / 1500 ккал (м).
    - Прогноз продолжается до достижения цели (не более 260 недель).
    """
    direction = _resolve_direction(current_weight, target_weight)
    if direction == "maintain":
        today = datetime.now().date()
        return [{"week": 0, "date": today.isoformat(), "weight_kg": round(current_weight, 2)}]

    mode_typed: Mode = mode if mode in {"light", "medium", "hard"} else "medium"
    activity_typed: ActivityLevel = (
        activity_level if activity_level in ACTIVITY_MULTIPLIERS else "moderate"
    )

    distance_total = abs(current_weight - target_weight)
    if distance_total < 0.01:
        today = datetime.now().date()
        return [{"week": 0, "date": today.isoformat(), "weight_kg": round(current_weight, 2)}]

    base_delta = _base_delta_kcal(direction, mode_typed)
    floor_kcal = _calorie_floor(gender)

    weight = float(current_weight)
    date_cursor = datetime.now().date()
    result = [{"week": 0, "date": date_cursor.isoformat(), "weight_kg": round(weight, 2)}]

    for week in range(1, _MAX_FORECAST_WEEKS + 1):
        if abs(weight - target_weight) <= 0.05:
            break

        bmr = calculate_bmr(gender=gender, age=age, height_cm=height_cm, weight_kg=weight)  # type: ignore[arg-type]
        tdee = bmr * ACTIVITY_MULTIPLIERS[activity_typed]

        # Адаптивный термогенез: после 8 недель дефицита тело экономит до 5% энергии.
        if week > 8 and direction == "lose":
            adapt_reduction = min(0.05, 0.005 * (week - 8))
            effective_tdee = tdee * (1.0 - adapt_reduction)
        else:
            effective_tdee = tdee

        # Целевая калорийность = эффективный TDEE + фиксированный дефицит
        calories_target = effective_tdee + base_delta
        calories_target = max(calories_target, floor_kcal)

        # Фактический ежедневный баланс (после клемпа)
        actual_daily_delta = calories_target - effective_tdee

        weekly_change = (actual_daily_delta * 7.0) / 7700.0
        if direction == "lose":
            weekly_change = min(0.0, weekly_change)
        else:
            weekly_change = max(0.0, weekly_change)

        next_weight = weight + weekly_change
        if direction == "lose" and next_weight < target_weight:
            next_weight = target_weight
        if direction == "gain" and next_weight > target_weight:
            next_weight = target_weight

        weight = next_weight
        date_cursor += timedelta(days=7)
        result.append({"week": week, "date": date_cursor.isoformat(), "weight_kg": round(weight, 2)})

    return result


def calculate_plan_targets(
    current_weight: float,
    target_weight: float,
    gender: str,
    age: int,
    height_cm: float,
    activity_level: str,
    mode: str,
) -> dict:
    direction = _resolve_direction(current_weight, target_weight)
    mode_typed: Mode = mode if mode in {"light", "medium", "hard"} else "medium"
    activity_typed: ActivityLevel = (
        activity_level if activity_level in ACTIVITY_MULTIPLIERS else "moderate"
    )

    bmr = calculate_bmr(gender=gender, age=age, height_cm=height_cm, weight_kg=current_weight)  # type: ignore[arg-type]
    tdee = bmr * ACTIVITY_MULTIPLIERS[activity_typed]
    base_delta = _base_delta_kcal(direction, mode_typed)
    calories = tdee + base_delta
    calories = max(calories, _calorie_floor(gender))

    if direction == "lose":
        protein_per_kg = {"light": 1.6, "medium": 1.9, "hard": 2.2}[mode_typed]
    else:
        protein_per_kg = {"light": 1.6, "medium": 1.8, "hard": 2.0}[mode_typed]

    protein_g = max(0.0, protein_per_kg * current_weight)
    fat_g = max(0.8 * current_weight, 0.0)
    kcal_after_pf = calories - (protein_g * 4.0 + fat_g * 9.0)
    carbs_g = max(0.0, kcal_after_pf / 4.0)

    # Скорость из реального дефицита (после клемпа калорий)
    actual_delta = calories - tdee
    weekly_loss_kg = abs(actual_delta) * 7.0 / 7700.0

    distance = abs(current_weight - target_weight)
    estimated_weeks = int(math.ceil(distance / weekly_loss_kg)) if weekly_loss_kg > 0 else 0

    return {
        "daily_calories": round(calories, 1),
        "daily_protein": round(protein_g, 1),
        "daily_fat": round(fat_g, 1),
        "daily_carbs": round(carbs_g, 1),
        "estimated_weeks": int(estimated_weeks),
        "weekly_loss_kg": round(weekly_loss_kg, 3),
        "daily_deficit": round(abs(base_delta), 1),
    }


def get_expected_weight_for_date(
    plan_start_date: datetime,
    plan_start_kg: float,
    target_weight: float,
    mode: str,
    gender: str,
    age: int,
    height_cm: float,
    activity_level: str,
    check_date: datetime,
) -> float:
    forecast = build_weight_forecast(
        current_weight=plan_start_kg,
        target_weight=target_weight,
        gender=gender,
        age=age,
        height_cm=height_cm,
        activity_level=activity_level,
        mode=mode,
    )
    days_delta = max(0, (check_date.date() - plan_start_date.date()).days)
    week_idx = days_delta // 7
    if week_idx >= len(forecast):
        return float(forecast[-1]["weight_kg"])

    if days_delta % 7 == 0 or week_idx == len(forecast) - 1:
        return float(forecast[week_idx]["weight_kg"])

    left = forecast[week_idx]
    right = forecast[week_idx + 1]
    ratio = (days_delta % 7) / 7.0
    interpolated = float(left["weight_kg"]) + (float(right["weight_kg"]) - float(left["weight_kg"])) * ratio
    return round(interpolated, 2)


def compare_progress(
    expected_kg: float,
    actual_kg: float,
    target_weight: float,
    current_weight: float,
) -> dict:
    direction = _resolve_direction(current_weight, target_weight)
    if direction == "lose":
        deviation_kg = actual_kg - expected_kg
        on_track = deviation_kg <= 0.5
    elif direction == "gain":
        deviation_kg = expected_kg - actual_kg
        on_track = deviation_kg <= 0.5
    else:
        deviation_kg = abs(actual_kg - expected_kg)
        on_track = deviation_kg <= 0.3

    base = max(abs(expected_kg), 0.1)
    deviation_pct = (deviation_kg / base) * 100.0

    if on_track:
        recommendation = "Ты движешься по плану. Сохраняй текущий режим и регулярность."
    else:
        recommendation = (
            "Есть отставание от плана. Проверь соблюдение калорийности, белка и уровень ежедневной активности."
        )

    return {
        "on_track": bool(on_track),
        "deviation_kg": round(float(deviation_kg), 2),
        "deviation_pct": round(float(deviation_pct), 2),
        "recommendation": recommendation,
    }
