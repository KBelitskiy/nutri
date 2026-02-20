from __future__ import annotations

from typing import Any
from zoneinfo import available_timezones

from sqlalchemy.ext.asyncio import async_sessionmaker

from bot.database import crud
from bot.services.nutrition import calculate_daily_targets

_VALID_GENDERS = {"male", "female"}
_VALID_ACTIVITIES = {"low", "light", "moderate", "high", "very_high"}
_VALID_GOALS = {"lose", "maintain", "gain"}


def user_tools_schema() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "get_user_profile",
                "description": "Возвращает профиль пользователя (пол, возраст, рост, стартовый вес, активность, цель, таймзона)",
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
        {
            "type": "function",
            "function": {
                "name": "update_user_profile",
                "description": (
                    "Обновляет поля профиля пользователя и пересчитывает суточные цели КБЖУ. "
                    "Доступные поля: gender (male/female), age (10-100), height_cm (100-250), "
                    "weight_start_kg (30-350), activity_level (low/light/moderate/high/very_high), "
                    "goal (lose/maintain/gain), timezone (IANA, например Europe/Moscow)"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "telegram_id": {"type": "integer"},
                        "fields": {
                            "type": "object",
                            "description": "Поля для обновления, например {\"age\": 30, \"goal\": \"lose\"}",
                        },
                    },
                    "required": ["telegram_id", "fields"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "reset_user_data",
                "description": "Удаляет все данные пользователя: профиль, питание, вес, историю и достижения.",
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
                "timezone": user.timezone,
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

    async def update_user_profile(args: dict[str, Any]) -> dict[str, Any]:
        tid = int(args["telegram_id"])
        fields = dict(args.get("fields") or {})
        if not fields:
            return {"error": "No fields provided"}

        async with sessionmaker() as session:
            user = await crud.get_user(session, tid)
            if user is None:
                return {"error": "User not found"}

            for key, value in fields.items():
                if key == "gender":
                    if str(value) not in _VALID_GENDERS:
                        return {"error": "gender must be male or female"}
                    user.gender = str(value)
                elif key == "age":
                    v = int(value)
                    if v < 10 or v > 100:
                        return {"error": "age must be 10..100"}
                    user.age = v
                elif key == "height_cm":
                    v = float(value)
                    if v < 100 or v > 250:
                        return {"error": "height_cm must be 100..250"}
                    user.height_cm = v
                elif key == "weight_start_kg":
                    v = float(value)
                    if v < 30 or v > 350:
                        return {"error": "weight_start_kg must be 30..350"}
                    user.weight_start_kg = v
                elif key == "activity_level":
                    if str(value) not in _VALID_ACTIVITIES:
                        return {"error": f"activity_level must be one of {_VALID_ACTIVITIES}"}
                    user.activity_level = str(value)
                elif key == "goal":
                    if str(value) not in _VALID_GOALS:
                        return {"error": f"goal must be one of {_VALID_GOALS}"}
                    user.goal = str(value)
                elif key == "timezone":
                    if str(value) not in available_timezones():
                        return {"error": f"Unknown timezone: {value}"}
                    user.timezone = str(value)
                else:
                    return {"error": f"Unknown field: {key}"}

            targets = calculate_daily_targets(
                gender=user.gender,  # type: ignore[arg-type]
                age=user.age,
                height_cm=user.height_cm,
                weight_kg=user.weight_start_kg,
                activity_level=user.activity_level,  # type: ignore[arg-type]
                goal=user.goal,  # type: ignore[arg-type]
            )
            user.daily_calories_target = targets["daily_calories_target"]
            user.daily_protein_target = targets["daily_protein_target"]
            user.daily_fat_target = targets["daily_fat_target"]
            user.daily_carbs_target = targets["daily_carbs_target"]
            await session.commit()

        return {
            "ok": True,
            "updated_fields": list(fields.keys()),
            "new_targets": targets,
        }

    async def reset_user_data(args: dict[str, Any]) -> dict[str, Any]:
        tid = int(args["telegram_id"])
        async with sessionmaker() as session:
            user = await crud.get_user(session, tid)
            if user is None:
                return {"error": "User not found"}
            await crud.delete_user_data(session, tid)
        return {"ok": True}

    return {
        "get_user_profile": get_user_profile,
        "get_daily_targets": get_daily_targets,
        "update_user_profile": update_user_profile,
        "reset_user_data": reset_user_data,
    }

