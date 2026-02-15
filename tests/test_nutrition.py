"""Тесты расчёта BMR, суточных целей и прогресса (bot.services.nutrition)."""
from __future__ import annotations

import pytest

from bot.services.nutrition import (
    calculate_bmr,
    calculate_daily_targets,
    summarize_progress,
)


class TestCalculateBmr:
    """Тесты формулы Миффлина-Сан Жеора (BMR)."""

    def test_male_basic(self) -> None:
        # мужчина 30 лет, 180 см, 80 кг
        bmr = calculate_bmr("male", 30, 180.0, 80.0)
        assert 1700 < bmr < 1900

    def test_female_basic(self) -> None:
        # женщина 25 лет, 165 см, 60 кг
        bmr = calculate_bmr("female", 25, 165.0, 60.0)
        assert 1200 < bmr < 1500

    def test_female_lower_than_male_same_params(self) -> None:
        bmr_m = calculate_bmr("male", 40, 170.0, 70.0)
        bmr_f = calculate_bmr("female", 40, 170.0, 70.0)
        assert bmr_f < bmr_m

    def test_age_reduces_bmr(self) -> None:
        young = calculate_bmr("male", 20, 175.0, 75.0)
        old = calculate_bmr("male", 60, 175.0, 75.0)
        assert old < young


class TestCalculateDailyTargets:
    """Тесты расчёта суточных целей по калориям и КБЖУ."""

    def test_returns_all_keys(self) -> None:
        t = calculate_daily_targets(
            gender="male",
            age=30,
            height_cm=180.0,
            weight_kg=80.0,
            activity_level="moderate",
            goal="maintain",
        )
        assert "daily_calories_target" in t
        assert "daily_protein_target" in t
        assert "daily_fat_target" in t
        assert "daily_carbs_target" in t

    def test_maintain_calories_above_bmr_times_activity(self) -> None:
        t = calculate_daily_targets(
            gender="male",
            age=30,
            height_cm=180.0,
            weight_kg=80.0,
            activity_level="light",
            goal="maintain",
        )
        bmr = calculate_bmr("male", 30, 180.0, 80.0)
        expected_min = bmr * 1.375  # light
        assert t["daily_calories_target"] >= expected_min * 0.9

    def test_lose_lower_than_maintain(self) -> None:
        maintain = calculate_daily_targets(
            gender="female", age=25, height_cm=165.0, weight_kg=60.0,
            activity_level="moderate", goal="maintain",
        )
        lose = calculate_daily_targets(
            gender="female", age=25, height_cm=165.0, weight_kg=60.0,
            activity_level="moderate", goal="lose",
        )
        assert lose["daily_calories_target"] < maintain["daily_calories_target"]

    def test_gain_higher_than_maintain(self) -> None:
        maintain = calculate_daily_targets(
            gender="male", age=30, height_cm=175.0, weight_kg=70.0,
            activity_level="moderate", goal="maintain",
        )
        gain = calculate_daily_targets(
            gender="male", age=30, height_cm=175.0, weight_kg=70.0,
            activity_level="moderate", goal="gain",
        )
        assert gain["daily_calories_target"] > maintain["daily_calories_target"]

    def test_calories_floor_1200(self) -> None:
        # очень низкие параметры не должны дать калории ниже 1200
        t = calculate_daily_targets(
            gender="female",
            age=80,
            height_cm=150.0,
            weight_kg=45.0,
            activity_level="low",
            goal="lose",
        )
        assert t["daily_calories_target"] >= 1200.0

    def test_protein_fat_carbs_positive(self) -> None:
        t = calculate_daily_targets(
            gender="male", age=30, height_cm=180.0, weight_kg=80.0,
            activity_level="moderate", goal="maintain",
        )
        assert t["daily_protein_target"] > 0
        assert t["daily_fat_target"] > 0
        assert t["daily_carbs_target"] > 0


class TestSummarizeProgress:
    """Тесты сводки прогресса (процент от цели, остаток)."""

    def test_zero_consumed(self) -> None:
        targets = {
            "daily_calories_target": 2000.0,
            "daily_protein_target": 100.0,
            "daily_fat_target": 65.0,
            "daily_carbs_target": 225.0,
        }
        p = summarize_progress({}, targets)
        assert p["calories_pct"] == 0.0
        assert p["calories_left"] == 2000.0
        assert p["protein_left"] == 100.0
        assert p["fat_left"] == 65.0
        assert p["carbs_left"] == 225.0

    def test_half_consumed(self) -> None:
        targets = {
            "daily_calories_target": 2000.0,
            "daily_protein_target": 100.0,
            "daily_fat_target": 65.0,
            "daily_carbs_target": 225.0,
        }
        consumed = {
            "calories": 1000.0,
            "protein_g": 50.0,
            "fat_g": 32.5,
            "carbs_g": 112.5,
        }
        p = summarize_progress(consumed, targets)
        assert p["calories_pct"] == 50.0
        assert p["calories_left"] == 1000.0
        assert p["protein_left"] == 50.0

    def test_over_target(self) -> None:
        targets = {"daily_calories_target": 2000.0, "daily_protein_target": 100.0, "daily_fat_target": 65.0, "daily_carbs_target": 225.0}
        consumed = {"calories": 2500.0, "protein_g": 120.0, "fat_g": 70.0, "carbs_g": 250.0}
        p = summarize_progress(consumed, targets)
        assert p["calories_pct"] == 125.0
        assert p["calories_left"] == -500.0

    def test_zero_targets_no_division_by_zero(self) -> None:
        p = summarize_progress({"calories": 100.0}, {"daily_calories_target": 0.0, "daily_protein_target": 0.0, "daily_fat_target": 0.0, "daily_carbs_target": 0.0})
        assert p["calories_pct"] == 0.0
        assert "calories_left" in p
