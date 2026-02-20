from __future__ import annotations

from typing import Literal

ActivityLevel = Literal["low", "light", "moderate", "high", "very_high"]
Goal = Literal["lose", "maintain", "gain"]
Gender = Literal["male", "female"]

ACTIVITY_MULTIPLIERS: dict[ActivityLevel, float] = {
    "low": 1.2,
    "light": 1.375,
    "moderate": 1.55,
    "high": 1.725,
    "very_high": 1.9,
}

GOAL_CALORIE_DELTA: dict[Goal, float] = {
    "lose": -300.0,
    "maintain": 0.0,
    "gain": 300.0,
}

GOAL_MACRO_SPLITS: dict[Goal, tuple[float, float, float]] = {
    "lose": (0.35, 0.30, 0.35),
    "maintain": (0.30, 0.25, 0.45),
    "gain": (0.30, 0.20, 0.50),
}


def calculate_bmr(gender: Gender, age: int, height_cm: float, weight_kg: float) -> float:
    base = 10 * weight_kg + 6.25 * height_cm - 5 * age
    if gender == "male":
        base += 5
    else:
        base -= 161
    return base


def calculate_daily_targets(
    gender: Gender,
    age: int,
    height_cm: float,
    weight_kg: float,
    activity_level: ActivityLevel,
    goal: Goal,
) -> dict[str, float]:
    bmr = calculate_bmr(gender, age, height_cm, weight_kg)
    calories = max(1200.0, bmr * ACTIVITY_MULTIPLIERS[activity_level] + GOAL_CALORIE_DELTA[goal])
    protein_ratio, fat_ratio, carbs_ratio = GOAL_MACRO_SPLITS[goal]
    protein_g = round((calories * protein_ratio) / 4, 1)
    fat_g = round((calories * fat_ratio) / 9, 1)
    carbs_g = round((calories * carbs_ratio) / 4, 1)
    return {
        "daily_calories_target": round(calories, 1),
        "daily_protein_target": protein_g,
        "daily_fat_target": fat_g,
        "daily_carbs_target": carbs_g,
    }


def summarize_progress(consumed: dict[str, float], targets: dict[str, float]) -> dict[str, float]:
    def pct(v: float, t: float) -> float:
        return round((v / t * 100.0), 1) if t > 0 else 0.0

    return {
        "calories_pct": pct(consumed.get("calories", 0.0), targets.get("daily_calories_target", 0.0)),
        "protein_pct": pct(consumed.get("protein_g", 0.0), targets.get("daily_protein_target", 0.0)),
        "fat_pct": pct(consumed.get("fat_g", 0.0), targets.get("daily_fat_target", 0.0)),
        "carbs_pct": pct(consumed.get("carbs_g", 0.0), targets.get("daily_carbs_target", 0.0)),
        "calories_left": round(targets.get("daily_calories_target", 0.0) - consumed.get("calories", 0.0), 1),
        "protein_left": round(targets.get("daily_protein_target", 0.0) - consumed.get("protein_g", 0.0), 1),
        "fat_left": round(targets.get("daily_fat_target", 0.0) - consumed.get("fat_g", 0.0), 1),
        "carbs_left": round(targets.get("daily_carbs_target", 0.0) - consumed.get("carbs_g", 0.0), 1),
    }

