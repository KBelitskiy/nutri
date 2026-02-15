"""Тесты утилит хендлеров: парсинг чисел, прогресс (bot.handlers.utils)."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from bot.database.models import MealLog, User
from bot.handlers.utils import (
    parse_float,
    parse_int,
    progress_text,
    today_with_meals_text,
    user_targets,
)


class TestParseFloat:
    def test_valid_integer_string(self) -> None:
        assert parse_float("42") == 42.0
        assert parse_float("0") == 0.0

    def test_valid_decimal(self) -> None:
        assert parse_float("3.14") == 3.14
        assert parse_float("70,5") == 70.5

    def test_comma_as_decimal_separator(self) -> None:
        assert parse_float("180,5") == 180.5

    def test_invalid_returns_none(self) -> None:
        assert parse_float("") is None
        assert parse_float("abc") is None
        assert parse_float("  ") is None


class TestParseInt:
    def test_valid(self) -> None:
        assert parse_int("30") == 30
        assert parse_int("  25  ") == 25

    def test_invalid_returns_none(self) -> None:
        assert parse_int("") is None
        assert parse_int("12.5") is None
        assert parse_int("abc") is None


class TestUserTargets:
    def test_returns_dict_with_targets(self) -> None:
        user = MagicMock(spec=User)
        user.daily_calories_target = 2000.0
        user.daily_protein_target = 100.0
        user.daily_fat_target = 65.0
        user.daily_carbs_target = 225.0
        t = user_targets(user)
        assert t["daily_calories_target"] == 2000.0
        assert t["daily_protein_target"] == 100.0
        assert t["daily_fat_target"] == 65.0
        assert t["daily_carbs_target"] == 225.0


class TestProgressText:
    def test_formats_progress_string(self) -> None:
        user = MagicMock(spec=User)
        user.daily_calories_target = 2000.0
        user.daily_protein_target = 100.0
        user.daily_fat_target = 65.0
        user.daily_carbs_target = 225.0
        consumed = {
            "calories": 1000.0,
            "protein_g": 50.0,
            "fat_g": 32.5,
            "carbs_g": 112.5,
        }
        text = progress_text(consumed, user)
        assert "1000.0" in text
        assert "2000.0" in text
        assert "50.0" in text
        assert "осталось" in text


class TestTodayWithMealsText:
    def test_empty_meals_includes_progress(self) -> None:
        user = MagicMock(spec=User)
        user.daily_calories_target = 2000.0
        user.daily_protein_target = 100.0
        user.daily_fat_target = 65.0
        user.daily_carbs_target = 225.0
        consumed = {"calories": 0.0, "protein_g": 0.0, "fat_g": 0.0, "carbs_g": 0.0}
        text = today_with_meals_text([], consumed, user)
        assert "Приёмы пищи за сегодня" in text
        assert "0.0" in text
        assert "2000.0" in text

    def test_with_meals_lists_each_with_calories(self) -> None:
        user = MagicMock(spec=User)
        user.daily_calories_target = 2000.0
        user.daily_protein_target = 100.0
        user.daily_fat_target = 65.0
        user.daily_carbs_target = 225.0
        m1 = MagicMock(spec=MealLog, description="Овсянка", calories=350.0)
        m2 = MagicMock(spec=MealLog, description="Салат", calories=120.0)
        consumed = {"calories": 470.0, "protein_g": 15.0, "fat_g": 10.0, "carbs_g": 60.0}
        text = today_with_meals_text([m1, m2], consumed, user)
        assert "Овсянка" in text and "350" in text
        assert "Салат" in text and "120" in text
        assert "470.0" in text
