"""Тесты tool handlers для пользователя (bot.tools.user_tools)."""
from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from bot.database import crud
from bot.tools.user_tools import user_tool_handlers


@pytest.fixture
def sample_user_data() -> dict:
    return {
        "telegram_id": 88888,
        "username": "profile_test",
        "gender": "female",
        "age": 26,
        "height_cm": 165.0,
        "weight_start_kg": 58.0,
        "activity_level": "light",
        "goal": "lose",
        "daily_calories_target": 1800.0,
        "daily_protein_target": 90.0,
        "daily_fat_target": 50.0,
        "daily_carbs_target": 200.0,
    }


async def test_get_user_profile_returns_error_when_not_found(
    sessionmaker: async_sessionmaker,
) -> None:
    handlers = user_tool_handlers(sessionmaker)
    result = await handlers["get_user_profile"]({"telegram_id": 999999})
    assert "error" in result
    assert result["error"] == "User not found"


async def test_get_user_profile_returns_data(
    sessionmaker: async_sessionmaker, sample_user_data: dict
) -> None:
    async with sessionmaker() as s:
        await crud.create_or_update_user(s, sample_user_data)
    handlers = user_tool_handlers(sessionmaker)
    result = await handlers["get_user_profile"]({"telegram_id": 88888})
    assert "error" not in result
    assert result["telegram_id"] == 88888
    assert result["username"] == "profile_test"
    assert result["gender"] == "female"
    assert result["goal"] == "lose"


async def test_get_daily_targets_returns_error_when_not_found(
    sessionmaker: async_sessionmaker,
) -> None:
    handlers = user_tool_handlers(sessionmaker)
    result = await handlers["get_daily_targets"]({"telegram_id": 999999})
    assert result.get("error") == "User not found"


async def test_get_daily_targets_returns_targets(
    sessionmaker: async_sessionmaker, sample_user_data: dict
) -> None:
    async with sessionmaker() as s:
        await crud.create_or_update_user(s, sample_user_data)
    handlers = user_tool_handlers(sessionmaker)
    result = await handlers["get_daily_targets"]({"telegram_id": 88888})
    assert result["daily_calories_target"] == 1800.0
    assert result["daily_protein_target"] == 90.0
    assert result["daily_fat_target"] == 50.0
    assert result["daily_carbs_target"] == 200.0
