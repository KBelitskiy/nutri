"""Тесты tool handlers для приёмов пищи (bot.tools.meal_tools)."""
from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from bot.database import crud
from bot.tools.meal_tools import meal_tool_handlers


@pytest.fixture
def sample_user_data() -> dict:
    return {
        "telegram_id": 77777,
        "username": "meal_test",
        "gender": "male",
        "age": 28,
        "height_cm": 178.0,
        "weight_start_kg": 75.0,
        "activity_level": "moderate",
        "goal": "maintain",
        "daily_calories_target": 2400.0,
        "daily_protein_target": 110.0,
        "daily_fat_target": 65.0,
        "daily_carbs_target": 270.0,
    }


async def test_add_meal_returns_ok_and_meal_id(
    sessionmaker: async_sessionmaker, sample_user_data: dict
) -> None:
    async with sessionmaker() as s:
        await crud.create_or_update_user(s, sample_user_data)
    handlers = meal_tool_handlers(sessionmaker)
    result = await handlers["add_meal"](
        {
            "telegram_id": 77777,
            "description": "овсянка с бананом",
            "calories": 350.0,
            "protein_g": 10.0,
            "fat_g": 8.0,
            "carbs_g": 55.0,
            "meal_type": "breakfast",
        }
    )
    assert result["ok"] is True
    assert "meal_id" in result
    assert isinstance(result["meal_id"], int)


async def test_get_meals_today_returns_list(
    sessionmaker: async_sessionmaker, sample_user_data: dict
) -> None:
    async with sessionmaker() as s:
        await crud.create_or_update_user(s, sample_user_data)
        await crud.add_meal_log(s, 77777, "обед", 500.0, 25.0, 20.0, 50.0)
    handlers = meal_tool_handlers(sessionmaker)
    result = await handlers["get_meals_today"]({"telegram_id": 77777})
    assert "meals" in result
    assert len(result["meals"]) >= 1
    meal = result["meals"][0]
    assert "id" in meal
    assert meal["description"] == "обед"
    assert meal["calories"] == 500.0


async def test_delete_meal(
    sessionmaker: async_sessionmaker, sample_user_data: dict
) -> None:
    async with sessionmaker() as s:
        await crud.create_or_update_user(s, sample_user_data)
        row = await crud.add_meal_log(s, 77777, "удалить", 100.0, 1.0, 1.0, 1.0)
    handlers = meal_tool_handlers(sessionmaker)
    result = await handlers["delete_meal"]({"telegram_id": 77777, "meal_id": row.id})
    assert result["ok"] is True


async def test_update_meal(
    sessionmaker: async_sessionmaker, sample_user_data: dict
) -> None:
    async with sessionmaker() as s:
        await crud.create_or_update_user(s, sample_user_data)
        row = await crud.add_meal_log(s, 77777, "старое", 200.0, 5.0, 5.0, 25.0)
    handlers = meal_tool_handlers(sessionmaker)
    result = await handlers["update_meal"](
        {
            "telegram_id": 77777,
            "meal_id": row.id,
            "fields": {"description": "обновлённое", "calories": 250.0},
        }
    )
    assert result["ok"] is True
