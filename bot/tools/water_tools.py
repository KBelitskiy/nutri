from __future__ import annotations

from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import async_sessionmaker

from bot.database import crud


def water_tools_schema() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "add_water",
                "description": "Добавляет запись о выпитой воде в мл и возвращает прогресс за сегодня.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "telegram_id": {"type": "integer"},
                        "amount_ml": {"type": "integer"},
                    },
                    "required": ["telegram_id", "amount_ml"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_water_today",
                "description": "Возвращает, сколько воды выпито за сегодня и дневную цель в мл.",
                "parameters": {
                    "type": "object",
                    "properties": {"telegram_id": {"type": "integer"}},
                    "required": ["telegram_id"],
                },
            },
        },
    ]


def water_tool_handlers(
    sessionmaker: async_sessionmaker,
    *,
    timezone_name: str = "UTC",
) -> dict[str, Any]:
    default_tz = ZoneInfo(timezone_name)

    async def add_water(args: dict[str, Any]) -> dict[str, Any]:
        tid = int(args["telegram_id"])
        amount_ml = max(1, int(args.get("amount_ml", 250)))
        async with sessionmaker() as session:
            user = await crud.get_user(session, tid)
            if user is None:
                return {"error": "User not found"}
            if user.daily_water_target_ml is None:
                user.daily_water_target_ml = max(1200, int(float(user.weight_start_kg) * 30))
                await session.commit()
            tz = default_tz
            if user.timezone:
                try:
                    tz = ZoneInfo(user.timezone)
                except Exception:  # noqa: BLE001
                    tz = default_tz
            await crud.add_water_log(session, tid, amount_ml)
            total_ml = await crud.get_water_summary_for_day(session, tid, timezone=tz)
            target_ml = int(user.daily_water_target_ml or max(1200, int(float(user.weight_start_kg) * 30)))
            return {
                "ok": True,
                "added_ml": amount_ml,
                "today_ml": total_ml,
                "target_ml": target_ml,
                "left_ml": max(0, target_ml - total_ml),
                "progress_pct": round((total_ml / target_ml * 100.0), 1) if target_ml > 0 else 0.0,
            }

    async def get_water_today(args: dict[str, Any]) -> dict[str, Any]:
        tid = int(args["telegram_id"])
        async with sessionmaker() as session:
            user = await crud.get_user(session, tid)
            if user is None:
                return {"error": "User not found"}
            if user.daily_water_target_ml is None:
                user.daily_water_target_ml = max(1200, int(float(user.weight_start_kg) * 30))
                await session.commit()
            tz = default_tz
            if user.timezone:
                try:
                    tz = ZoneInfo(user.timezone)
                except Exception:  # noqa: BLE001
                    tz = default_tz
            total_ml = await crud.get_water_summary_for_day(session, tid, timezone=tz)
            target_ml = int(user.daily_water_target_ml or max(1200, int(float(user.weight_start_kg) * 30)))
            return {
                "today_ml": total_ml,
                "target_ml": target_ml,
                "left_ml": max(0, target_ml - total_ml),
                "progress_pct": round((total_ml / target_ml * 100.0), 1) if target_ml > 0 else 0.0,
            }

    return {
        "add_water": add_water,
        "get_water_today": get_water_today,
    }
