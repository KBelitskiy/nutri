from __future__ import annotations

from zoneinfo import ZoneInfo
from typing import Any

from sqlalchemy.ext.asyncio import async_sessionmaker

from bot.database import crud
from bot.services.nutrition import summarize_progress


def meal_tools_schema() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "add_meal",
                "description": "Добавляет прием пищи. Возвращает daily_summary с текущим потреблением и целями.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "telegram_id": {"type": "integer"},
                        "description": {"type": "string", "description": "Описание блюда для дневника"},
                        "calories": {"type": "number"},
                        "protein_g": {"type": "number"},
                        "fat_g": {"type": "number"},
                        "carbs_g": {"type": "number"},
                        "meal_type": {
                            "type": "string",
                            "enum": ["breakfast", "lunch", "dinner", "snack"],
                        },
                    },
                    "required": ["telegram_id", "description", "calories", "protein_g", "fat_g", "carbs_g"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_meals_today",
                "description": "Возвращает список приемов пищи за сегодня с КБЖУ каждого",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "telegram_id": {"type": "integer"},
                    },
                    "required": ["telegram_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_today_summary",
                "description": (
                    "Возвращает полную сводку за сегодня: список приемов пищи, "
                    "суммарное потребление КБЖУ, дневные цели и прогресс (процент, остаток)"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "telegram_id": {"type": "integer"},
                    },
                    "required": ["telegram_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "delete_meal",
                "description": "Удаляет прием пищи по id. Используй get_meals_today чтобы узнать id нужного приема.",
                "parameters": {
                    "type": "object",
                    "properties": {"telegram_id": {"type": "integer"}, "meal_id": {"type": "integer"}},
                    "required": ["telegram_id", "meal_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "update_meal",
                "description": (
                    "Редактирует прием пищи по id. Можно обновить любые поля: "
                    "description, calories, protein_g, fat_g, carbs_g, meal_type"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "telegram_id": {"type": "integer"},
                        "meal_id": {"type": "integer"},
                        "fields": {
                            "type": "object",
                            "description": "Поля для обновления, например {\"calories\": 350, \"protein_g\": 25}",
                        },
                    },
                    "required": ["telegram_id", "meal_id", "fields"],
                },
            },
        },
    ]


def meal_tool_handlers(sessionmaker: async_sessionmaker, *, timezone_name: str = "UTC") -> dict[str, Any]:
    tz = ZoneInfo(timezone_name)

    async def add_meal(args: dict[str, Any]) -> dict[str, Any]:
        tid = int(args["telegram_id"])
        async with sessionmaker() as session:
            row = await crud.add_meal_log(
                session=session,
                telegram_id=tid,
                description=str(args["description"]),
                calories=float(args["calories"]),
                protein_g=float(args["protein_g"]),
                fat_g=float(args["fat_g"]),
                carbs_g=float(args["carbs_g"]),
                meal_type=str(args.get("meal_type", "snack")),
            )
            user = await crud.get_user(session, tid)
            consumed = await crud.get_meal_summary_for_day(session, tid, timezone=tz)

        result: dict[str, Any] = {"ok": True, "meal_id": row.id}
        if user is not None:
            targets = {
                "daily_calories_target": user.daily_calories_target,
                "daily_protein_target": user.daily_protein_target,
                "daily_fat_target": user.daily_fat_target,
                "daily_carbs_target": user.daily_carbs_target,
            }
            progress = summarize_progress(consumed, targets)
            result["daily_summary"] = {
                "consumed": consumed,
                "targets": targets,
                "progress": progress,
            }
        return result

    async def get_meals_today(args: dict[str, Any]) -> dict[str, Any]:
        async with sessionmaker() as session:
            meals = await crud.get_meals_for_day(
                session,
                int(args["telegram_id"]),
                timezone=tz,
            )
            return {
                "meals": [
                    {
                        "id": m.id,
                        "description": m.description,
                        "calories": m.calories,
                        "protein_g": m.protein_g,
                        "fat_g": m.fat_g,
                        "carbs_g": m.carbs_g,
                        "meal_type": m.meal_type,
                        "logged_at": m.logged_at.isoformat() if m.logged_at else None,
                    }
                    for m in meals
                ]
            }

    async def get_today_summary(args: dict[str, Any]) -> dict[str, Any]:
        tid = int(args["telegram_id"])
        async with sessionmaker() as session:
            user = await crud.get_user(session, tid)
            if user is None:
                return {"error": "User not found"}
            consumed = await crud.get_meal_summary_for_day(session, tid, timezone=tz)
            meals = await crud.get_meals_for_day(session, tid, timezone=tz)

        targets = {
            "daily_calories_target": user.daily_calories_target,
            "daily_protein_target": user.daily_protein_target,
            "daily_fat_target": user.daily_fat_target,
            "daily_carbs_target": user.daily_carbs_target,
        }
        progress = summarize_progress(consumed, targets)
        return {
            "meals": [
                {
                    "id": m.id,
                    "description": m.description,
                    "calories": m.calories,
                    "protein_g": m.protein_g,
                    "fat_g": m.fat_g,
                    "carbs_g": m.carbs_g,
                    "meal_type": m.meal_type,
                }
                for m in meals
            ],
            "consumed": consumed,
            "targets": targets,
            "progress": progress,
        }

    async def delete_meal(args: dict[str, Any]) -> dict[str, Any]:
        async with sessionmaker() as session:
            ok = await crud.delete_meal_log(session, int(args["telegram_id"]), int(args["meal_id"]))
            return {"ok": ok}

    async def update_meal(args: dict[str, Any]) -> dict[str, Any]:
        async with sessionmaker() as session:
            ok = await crud.update_meal_log(
                session, int(args["telegram_id"]), int(args["meal_id"]), dict(args["fields"])
            )
            return {"ok": ok}

    return {
        "add_meal": add_meal,
        "get_meals_today": get_meals_today,
        "get_today_summary": get_today_summary,
        "delete_meal": delete_meal,
        "update_meal": update_meal,
    }

