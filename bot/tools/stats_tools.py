from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import async_sessionmaker

from bot.database import crud


def stats_tools_schema() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "get_stats",
                "description": "Возвращает статистику питания за период",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "telegram_id": {"type": "integer"},
                        "period": {"type": "string", "enum": ["day", "week", "month"]},
                        "date_from": {"type": "string"},
                        "date_to": {"type": "string"},
                    },
                    "required": ["telegram_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_nutrition_history",
                "description": (
                    "Возвращает историю питания за период: все приемы пищи, "
                    "подневные суммы КБЖУ, средние показатели и текущие цели пользователя"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "telegram_id": {"type": "integer"},
                        "days": {
                            "type": "integer",
                            "description": "Сколько последних дней анализировать (1..90). По умолчанию 7.",
                        },
                    },
                    "required": ["telegram_id"],
                },
            },
        },
    ]


def stats_tool_handlers(sessionmaker: async_sessionmaker) -> dict[str, Any]:
    async def get_stats(args: dict[str, Any]) -> dict[str, Any]:
        period = str(args.get("period", "week"))
        now = datetime.now(tz=UTC)
        if "date_from" in args and "date_to" in args:
            start = datetime.fromisoformat(str(args["date_from"]))
            end = datetime.fromisoformat(str(args["date_to"]))
        elif period == "day":
            start = now - timedelta(days=1)
            end = now
        elif period == "month":
            start = now - timedelta(days=30)
            end = now
        else:
            start = now - timedelta(days=7)
            end = now

        async with sessionmaker() as session:
            data = await crud.get_meal_stats(session, int(args["telegram_id"]), start, end)
            return {"period": period, "start": start.isoformat(), "end": end.isoformat(), **data}

    async def get_nutrition_history(args: dict[str, Any]) -> dict[str, Any]:
        tid = int(args["telegram_id"])
        days = int(args.get("days", 7))
        days = max(1, min(days, 90))
        end = datetime.now(tz=UTC)
        start = end - timedelta(days=days)

        async with sessionmaker() as session:
            user = await crud.get_user(session, tid)
            if user is None:
                return {"error": "User not found"}
            meals = await crud.get_meals_for_period(session, tid, start, end)
            averages = await crud.get_meal_stats(session, tid, start, end)

        daily_map: dict[str, dict[str, float]] = {}
        for meal in meals:
            if meal.logged_at is None:
                continue
            day_key = meal.logged_at.astimezone(UTC).date().isoformat()
            if day_key not in daily_map:
                daily_map[day_key] = {
                    "calories": 0.0,
                    "protein_g": 0.0,
                    "fat_g": 0.0,
                    "carbs_g": 0.0,
                    "meals_count": 0.0,
                }
            daily_map[day_key]["calories"] += float(meal.calories)
            daily_map[day_key]["protein_g"] += float(meal.protein_g)
            daily_map[day_key]["fat_g"] += float(meal.fat_g)
            daily_map[day_key]["carbs_g"] += float(meal.carbs_g)
            daily_map[day_key]["meals_count"] += 1.0

        daily_totals = []
        for day, totals in sorted(daily_map.items()):
            daily_totals.append(
                {
                    "date": day,
                    "calories": round(totals["calories"], 1),
                    "protein_g": round(totals["protein_g"], 1),
                    "fat_g": round(totals["fat_g"], 1),
                    "carbs_g": round(totals["carbs_g"], 1),
                    "meals_count": int(totals["meals_count"]),
                }
            )

        all_meals = [
            {
                "id": meal.id,
                "description": meal.description,
                "meal_type": meal.meal_type,
                "calories": meal.calories,
                "protein_g": meal.protein_g,
                "fat_g": meal.fat_g,
                "carbs_g": meal.carbs_g,
                "logged_at": meal.logged_at.isoformat() if meal.logged_at else None,
            }
            for meal in meals
        ]

        return {
            "period": {
                "date_from": start.date().isoformat(),
                "date_to": end.date().isoformat(),
                "total_days": days,
                "days_with_data": len(daily_totals),
            },
            "targets": {
                "daily_calories_target": user.daily_calories_target,
                "daily_protein_target": user.daily_protein_target,
                "daily_fat_target": user.daily_fat_target,
                "daily_carbs_target": user.daily_carbs_target,
            },
            "averages": averages,
            "daily_totals": daily_totals,
            "all_meals": all_meals,
        }

    return {"get_stats": get_stats, "get_nutrition_history": get_nutrition_history}

