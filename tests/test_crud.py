"""Тесты CRUD и вспомогательных функций (bot.database.crud)."""
from __future__ import annotations

from datetime import UTC, date, datetime, time

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database import crud
from bot.database.models import MealLog, User, WeightLog


@pytest.fixture
def sample_user_data() -> dict:
    return {
        "telegram_id": 12345,
        "username": "testuser",
        "gender": "male",
        "age": 30,
        "height_cm": 180.0,
        "weight_start_kg": 80.0,
        "activity_level": "moderate",
        "goal": "maintain",
        "daily_calories_target": 2500.0,
        "daily_protein_target": 120.0,
        "daily_fat_target": 70.0,
        "daily_carbs_target": 280.0,
    }


class TestDayBounds:
    def test_returns_start_end_for_given_date(self) -> None:
        d = date(2025, 2, 15)
        start, end = crud.day_bounds(d)
        assert start == datetime(2025, 2, 15, 0, 0, 0, tzinfo=UTC)
        assert end == datetime(2025, 2, 15, 23, 59, 59, 999999, tzinfo=UTC)

    def test_none_uses_today(self) -> None:
        start, end = crud.day_bounds(None)
        today = datetime.now(tz=UTC).date()
        assert start.date() == today
        assert end.date() == today


class TestGetUser:
    async def test_returns_none_when_no_user(self, session: AsyncSession) -> None:
        user = await crud.get_user(session, 99999)
        assert user is None

    async def test_returns_user_when_exists(
        self, session: AsyncSession, sample_user_data: dict
    ) -> None:
        await crud.create_or_update_user(session, sample_user_data)
        user = await crud.get_user(session, sample_user_data["telegram_id"])
        assert user is not None
        assert user.telegram_id == sample_user_data["telegram_id"]
        assert user.username == sample_user_data["username"]
        assert user.daily_calories_target == sample_user_data["daily_calories_target"]


class TestCreateOrUpdateUser:
    async def test_creates_new_user(
        self, session: AsyncSession, sample_user_data: dict
    ) -> None:
        user = await crud.create_or_update_user(session, sample_user_data)
        assert user.telegram_id == sample_user_data["telegram_id"]
        assert user.age == 30

    async def test_updates_existing_user(
        self, session: AsyncSession, sample_user_data: dict
    ) -> None:
        await crud.create_or_update_user(session, sample_user_data)
        sample_user_data["age"] = 31
        sample_user_data["daily_calories_target"] = 2400.0
        user = await crud.create_or_update_user(session, sample_user_data)
        assert user.age == 31
        assert user.daily_calories_target == 2400.0


class TestDeleteUserData:
    async def test_deletes_user_and_cleans(
        self, session: AsyncSession, sample_user_data: dict
    ) -> None:
        await crud.create_or_update_user(session, sample_user_data)
        tid = sample_user_data["telegram_id"]
        await crud.delete_user_data(session, tid)
        user = await crud.get_user(session, tid)
        assert user is None


class TestWeightLogs:
    async def test_add_and_get_weight_logs(
        self, session: AsyncSession, sample_user_data: dict
    ) -> None:
        await crud.create_or_update_user(session, sample_user_data)
        tid = sample_user_data["telegram_id"]
        await crud.add_weight_log(session, tid, 79.5)
        await crud.add_weight_log(session, tid, 79.0)
        logs = await crud.get_weight_logs(session, tid, limit=10)
        assert len(logs) == 2
        weights = {log.weight_kg for log in logs}
        assert weights == {79.0, 79.5}


class TestMealLogs:
    async def test_add_meal_log(
        self, session: AsyncSession, sample_user_data: dict
    ) -> None:
        await crud.create_or_update_user(session, sample_user_data)
        tid = sample_user_data["telegram_id"]
        row = await crud.add_meal_log(
            session, tid, "гречка и курица", 350.0, 25.0, 10.0, 40.0
        )
        assert row.id is not None
        assert row.description == "гречка и курица"
        assert row.calories == 350.0

    async def test_get_meals_for_day(
        self, session: AsyncSession, sample_user_data: dict
    ) -> None:
        await crud.create_or_update_user(session, sample_user_data)
        tid = sample_user_data["telegram_id"]
        await crud.add_meal_log(session, tid, "завтрак", 300.0, 15.0, 10.0, 35.0)
        today = datetime.now(tz=UTC).date()
        meals = await crud.get_meals_for_day(session, tid, today)
        assert len(meals) == 1
        assert meals[0].description == "завтрак"

    async def test_get_meal_summary_for_day(
        self, session: AsyncSession, sample_user_data: dict
    ) -> None:
        await crud.create_or_update_user(session, sample_user_data)
        tid = sample_user_data["telegram_id"]
        await crud.add_meal_log(session, tid, "а", 100.0, 5.0, 2.0, 10.0)
        await crud.add_meal_log(session, tid, "б", 200.0, 10.0, 4.0, 20.0)
        today = datetime.now(tz=UTC).date()
        summary = await crud.get_meal_summary_for_day(session, tid, today)
        assert summary["calories"] == 300.0
        assert summary["protein_g"] == 15.0
        assert summary["fat_g"] == 6.0
        assert summary["carbs_g"] == 30.0

    async def test_delete_meal_log(
        self, session: AsyncSession, sample_user_data: dict
    ) -> None:
        await crud.create_or_update_user(session, sample_user_data)
        tid = sample_user_data["telegram_id"]
        row = await crud.add_meal_log(session, tid, "удалить", 100.0, 1.0, 1.0, 1.0)
        ok = await crud.delete_meal_log(session, tid, row.id)
        assert ok is True
        today = datetime.now(tz=UTC).date()
        meals = await crud.get_meals_for_day(session, tid, today)
        assert len(meals) == 0

    async def test_update_meal_log(
        self, session: AsyncSession, sample_user_data: dict
    ) -> None:
        await crud.create_or_update_user(session, sample_user_data)
        tid = sample_user_data["telegram_id"]
        row = await crud.add_meal_log(session, tid, "старое", 100.0, 1.0, 1.0, 1.0)
        ok = await crud.update_meal_log(
            session, tid, row.id, {"description": "новое", "calories": 150.0}
        )
        assert ok is True
        user = await crud.get_user(session, tid)
        assert user is not None
        today = datetime.now(tz=UTC).date()
        meals = await crud.get_meals_for_day(session, tid, today)
        assert len(meals) == 1
        assert meals[0].description == "новое"
        assert meals[0].calories == 150.0


class TestGetMealStats:
    async def test_returns_zeros_when_no_meals(
        self, session: AsyncSession, sample_user_data: dict
    ) -> None:
        await crud.create_or_update_user(session, sample_user_data)
        tid = sample_user_data["telegram_id"]
        start = datetime(2025, 1, 1, tzinfo=UTC)
        end = datetime(2025, 1, 31, tzinfo=UTC)
        stats = await crud.get_meal_stats(session, tid, start, end)
        assert stats["avg_calories"] == 0.0
        assert stats["meals_count"] == 0

    async def test_returns_avg_when_meals_exist(
        self, session: AsyncSession, sample_user_data: dict
    ) -> None:
        await crud.create_or_update_user(session, sample_user_data)
        tid = sample_user_data["telegram_id"]
        await crud.add_meal_log(session, tid, "a", 200.0, 10.0, 5.0, 20.0)
        await crud.add_meal_log(session, tid, "b", 400.0, 20.0, 10.0, 40.0)
        start = datetime(2020, 1, 1, tzinfo=UTC)
        end = datetime(2030, 12, 31, tzinfo=UTC)
        stats = await crud.get_meal_stats(session, tid, start, end)
        assert stats["avg_calories"] == 300.0
        assert stats["meals_count"] == 2
