from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import async_sessionmaker

from bot.database import crud


def user_tools_schema() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "get_user_profile",
                "description": "Возвращает профиль пользователя",
                "parameters": {
                    "type": "object",
                    "properties": {"telegram_id": {"type": "integer"}},
                    "required": ["telegram_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_daily_targets",
                "description": "Возвращает дневные цели по калориям и БЖУ",
                "parameters": {
                    "type": "object",
                    "properties": {"telegram_id": {"type": "integer"}},
                    "required": ["telegram_id"],
                },
            },
        },
    ]


def user_tool_handlers(sessionmaker: async_sessionmaker) -> dict[str, Any]:
    async def get_user_profile(args: dict[str, Any]) -> dict[str, Any]:
        async with sessionmaker() as session:
            user = await crud.get_user(session, int(args["telegram_id"]))
            if user is None:
                return {"error": "User not found"}
            return {
                "telegram_id": user.telegram_id,
                "username": user.username,
                "gender": user.gender,
                "age": user.age,
                "height_cm": user.height_cm,
                "weight_start_kg": user.weight_start_kg,
                "activity_level": user.activity_level,
                "goal": user.goal,
            }

    async def get_daily_targets(args: dict[str, Any]) -> dict[str, Any]:
        async with sessionmaker() as session:
            user = await crud.get_user(session, int(args["telegram_id"]))
            if user is None:
                return {"error": "User not found"}
            return {
                "daily_calories_target": user.daily_calories_target,
                "daily_protein_target": user.daily_protein_target,
                "daily_fat_target": user.daily_fat_target,
                "daily_carbs_target": user.daily_carbs_target,
            }

    return {"get_user_profile": get_user_profile, "get_daily_targets": get_daily_targets}

