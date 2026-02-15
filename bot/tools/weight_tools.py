from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import async_sessionmaker

from bot.database import crud


def weight_tools_schema() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "record_weight",
                "description": "Сохраняет новое взвешивание",
                "parameters": {
                    "type": "object",
                    "properties": {"telegram_id": {"type": "integer"}, "weight_kg": {"type": "number"}},
                    "required": ["telegram_id", "weight_kg"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_weight_history",
                "description": "Возвращает историю веса",
                "parameters": {
                    "type": "object",
                    "properties": {"telegram_id": {"type": "integer"}, "limit": {"type": "integer"}},
                    "required": ["telegram_id"],
                },
            },
        },
    ]


def weight_tool_handlers(sessionmaker: async_sessionmaker) -> dict[str, Any]:
    async def record_weight(args: dict[str, Any]) -> dict[str, Any]:
        async with sessionmaker() as session:
            row = await crud.add_weight_log(session, int(args["telegram_id"]), float(args["weight_kg"]))
            return {"ok": True, "weight_log_id": row.id}

    async def get_weight_history(args: dict[str, Any]) -> dict[str, Any]:
        async with sessionmaker() as session:
            rows = await crud.get_weight_logs(
                session, int(args["telegram_id"]), int(args.get("limit", 30))
            )
            return {
                "weights": [
                    {"id": x.id, "weight_kg": x.weight_kg, "logged_at": x.logged_at.isoformat() if x.logged_at else None}
                    for x in rows
                ]
            }

    return {"record_weight": record_weight, "get_weight_history": get_weight_history}

