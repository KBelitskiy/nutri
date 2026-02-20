from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import async_sessionmaker

from bot.database import crud
from bot.services.streaks import get_streak_info


def streak_tools_schema() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "get_streak_info",
                "description": "Возвращает текущий стрик по дням и полученные бейджи пользователя.",
                "parameters": {
                    "type": "object",
                    "properties": {"telegram_id": {"type": "integer"}},
                    "required": ["telegram_id"],
                },
            },
        }
    ]


def streak_tool_handlers(sessionmaker: async_sessionmaker) -> dict[str, Any]:
    async def _get_streak_info(args: dict[str, Any]) -> dict[str, Any]:
        tid = int(args["telegram_id"])
        async with sessionmaker() as session:
            user = await crud.get_user(session, tid)
            if user is None:
                return {"error": "User not found"}
            info = await get_streak_info(session, tid)
            return {"ok": True, **info}

    return {"get_streak_info": _get_streak_info}
