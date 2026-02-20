from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import async_sessionmaker

from bot.database import crud
from bot.services.league_reports import build_daily_league_report, build_weekly_league_report


def group_tools_schema() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "get_group_league_today",
                "description": "Возвращает дневную лиговую сводку для текущего группового чата.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "telegram_id": {"type": "integer"},
                        "chat_id": {"type": "integer"},
                    },
                    "required": ["telegram_id", "chat_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_group_league_week",
                "description": "Возвращает недельную лиговую сводку для текущего группового чата.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "telegram_id": {"type": "integer"},
                        "chat_id": {"type": "integer"},
                    },
                    "required": ["telegram_id", "chat_id"],
                },
            },
        },
    ]


def group_tool_handlers(
    sessionmaker: async_sessionmaker,
    *,
    timezone_name: str,
) -> dict[str, Any]:
    async def get_group_league_today(args: dict[str, Any]) -> dict[str, Any]:
        tid = int(args["telegram_id"])
        chat_id = int(args["chat_id"])
        async with sessionmaker() as session:
            await crud.add_group_chat(session, chat_id)
            await crud.ensure_group_member(session, chat_id, tid)
            report = await build_daily_league_report(session, chat_id, timezone_name)
            return {"report": report or "Сегодня нет данных для сводки."}

    async def get_group_league_week(args: dict[str, Any]) -> dict[str, Any]:
        tid = int(args["telegram_id"])
        chat_id = int(args["chat_id"])
        async with sessionmaker() as session:
            await crud.add_group_chat(session, chat_id)
            await crud.ensure_group_member(session, chat_id, tid)
            report = await build_weekly_league_report(session, chat_id, timezone_name)
            return {"report": report or "За неделю нет данных для сводки."}

    return {
        "get_group_league_today": get_group_league_today,
        "get_group_league_week": get_group_league_week,
    }
