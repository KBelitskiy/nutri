"""Тесты tool handlers для веса (bot.tools.weight_tools)."""
from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from bot.database import crud
from bot.tools.weight_tools import weight_tool_handlers


@pytest.fixture
def sample_user_data() -> dict:
    return {
        "telegram_id": 99999,
        "username": "weight_test",
        "gender": "male",
        "age": 35,
        "height_cm": 182.0,
        "weight_start_kg": 85.0,
        "activity_level": "high",
        "goal": "maintain",
        "daily_calories_target": 2600.0,
        "daily_protein_target": 130.0,
        "daily_fat_target": 72.0,
        "daily_carbs_target": 290.0,
    }


async def test_record_weight_returns_ok_and_id(
    sessionmaker: async_sessionmaker, sample_user_data: dict
) -> None:
    async with sessionmaker() as s:
        await crud.create_or_update_user(s, sample_user_data)
    handlers = weight_tool_handlers(sessionmaker)
    result = await handlers["record_weight"]({"telegram_id": 99999, "weight_kg": 84.5})
    assert result["ok"] is True
    assert "weight_log_id" in result


async def test_get_weight_history_returns_list(
    sessionmaker: async_sessionmaker, sample_user_data: dict
) -> None:
    async with sessionmaker() as s:
        await crud.create_or_update_user(s, sample_user_data)
        await crud.add_weight_log(s, 99999, 84.0)
        await crud.add_weight_log(s, 99999, 83.5)
    handlers = weight_tool_handlers(sessionmaker)
    result = await handlers["get_weight_history"]({"telegram_id": 99999})
    assert "weights" in result
    assert len(result["weights"]) >= 2
    weights = [w["weight_kg"] for w in result["weights"]]
    assert 84.0 in weights and 83.5 in weights


async def test_get_weight_history_respects_limit(
    sessionmaker: async_sessionmaker, sample_user_data: dict
) -> None:
    async with sessionmaker() as s:
        await crud.create_or_update_user(s, sample_user_data)
        for w in [85.0, 84.5, 84.0, 83.5]:
            await crud.add_weight_log(s, 99999, w)
    handlers = weight_tool_handlers(sessionmaker)
    result = await handlers["get_weight_history"]({"telegram_id": 99999, "limit": 2})
    assert len(result["weights"]) == 2
