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
        }
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

    return {"get_stats": get_stats}

