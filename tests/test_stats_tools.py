"""Тесты tool handlers для статистики (bot.tools.stats_tools)."""
from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from bot.database import crud
from bot.tools.stats_tools import stats_tool_handlers, stats_tools_schema


def test_stats_tools_schema_has_get_stats() -> None:
    schema = stats_tools_schema()
    names = [s["function"]["name"] for s in schema if s.get("type") == "function"]
    assert "get_stats" in names


async def test_get_stats_returns_period_and_aggregates(
    sessionmaker: async_sessionmaker, sample_user_data: dict
) -> None:
    async with sessionmaker() as s:
        await crud.create_or_update_user(s, sample_user_data)
        await crud.add_meal_log(s, 88888, "обед", 500.0, 25.0, 20.0, 50.0)
    handlers = stats_tool_handlers(sessionmaker)
    result = await handlers["get_stats"]({"telegram_id": 88888})
    assert "period" in result
    assert "start" in result
    assert "end" in result
    assert "avg_calories" in result
    assert "avg_protein_g" in result
    assert "meals_count" in result


async def test_get_stats_period_day(sessionmaker: async_sessionmaker) -> None:
    handlers = stats_tool_handlers(sessionmaker)
    result = await handlers["get_stats"]({"telegram_id": 1, "period": "day"})
    assert result["period"] == "day"


async def test_get_stats_period_month(sessionmaker: async_sessionmaker) -> None:
    handlers = stats_tool_handlers(sessionmaker)
    result = await handlers["get_stats"]({"telegram_id": 1, "period": "month"})
    assert result["period"] == "month"


async def test_get_stats_with_date_range(sessionmaker: async_sessionmaker) -> None:
    handlers = stats_tool_handlers(sessionmaker)
    result = await handlers["get_stats"]({
        "telegram_id": 1,
        "date_from": "2025-01-01T00:00:00+00:00",
        "date_to": "2025-01-31T23:59:59+00:00",
    })
    assert "start" in result
    assert "2025-01-01" in result["start"]
    assert "2025-01-31" in result["end"]


@pytest.fixture
def sample_user_data() -> dict:
    return {
        "telegram_id": 88888,
        "username": "stats_test",
        "gender": "male",
        "age": 30,
        "height_cm": 178.0,
        "weight_start_kg": 75.0,
        "activity_level": "moderate",
        "goal": "maintain",
        "daily_calories_target": 2400.0,
        "daily_protein_target": 110.0,
        "daily_fat_target": 65.0,
        "daily_carbs_target": 270.0,
    }
