from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import async_sessionmaker

from bot.database import crud
from bot.services.chart import render_three_scenarios_chart, render_weight_plan_chart
from bot.services.pending_media import PendingPhoto, add_pending_photo
from bot.services.weight_plan import (
    build_weight_forecast,
    calculate_plan_targets,
    compare_progress,
    get_expected_weight_for_date,
)

_MODES = ("light", "medium", "hard")


def goal_tools_schema() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "set_weight_goal",
                "description": "Устанавливает целевой вес и показывает 3 сценария (лайт/медиум/хард).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "telegram_id": {"type": "integer"},
                        "target_weight_kg": {"type": "number"},
                    },
                    "required": ["telegram_id", "target_weight_kg"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "select_weight_plan_mode",
                "description": "Выбирает режим плана (light/medium/hard), фиксирует старт плана и пересчитывает КБЖУ.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "telegram_id": {"type": "integer"},
                        "mode": {"type": "string", "enum": ["light", "medium", "hard"]},
                    },
                    "required": ["telegram_id", "mode"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_weight_plan_status",
                "description": "Возвращает текущий статус плана по весу и отклонение от прогноза.",
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
                "name": "get_weight_plan_forecast",
                "description": "Возвращает прогноз плана и историю фактических замеров веса.",
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
                "name": "adjust_plan_targets",
                "description": "Корректирует план КБЖУ при отставании от графика в безопасных пределах.",
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
                "name": "get_exercise_recommendations",
                "description": "Возвращает профиль и контекст для рекомендаций по тренировкам.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "telegram_id": {"type": "integer"},
                        "focus": {
                            "type": "string",
                            "enum": ["cardio", "strength", "flexibility", "general"],
                        },
                    },
                    "required": ["telegram_id"],
                },
            },
        },
    ]


def goal_tool_handlers(sessionmaker: async_sessionmaker) -> dict[str, Any]:
    async def set_weight_goal(args: dict[str, Any]) -> dict[str, Any]:
        tid = int(args["telegram_id"])
        target_weight = float(args["target_weight_kg"])

        async with sessionmaker() as session:
            user = await crud.get_user(session, tid)
            if user is None:
                return {"error": "User not found. Сначала пройди /start."}

            latest = await crud.get_latest_weight(session, tid)
            current_weight = float(latest.weight_kg if latest else user.weight_start_kg)
            direction = "maintain"
            if target_weight < current_weight - 0.01:
                direction = "lose"
            elif target_weight > current_weight + 0.01:
                direction = "gain"

            user.target_weight_kg = target_weight
            user.goal = direction
            await session.commit()

            scenarios: dict[str, dict[str, Any]] = {}
            forecasts: dict[str, list[dict]] = {}
            for mode in _MODES:
                plan = calculate_plan_targets(
                    current_weight=current_weight,
                    target_weight=target_weight,
                    gender=user.gender,
                    age=user.age,
                    height_cm=user.height_cm,
                    activity_level=user.activity_level,
                    mode=mode,
                )
                forecast = build_weight_forecast(
                    current_weight=current_weight,
                    target_weight=target_weight,
                    gender=user.gender,
                    age=user.age,
                    height_cm=user.height_cm,
                    activity_level=user.activity_level,
                    mode=mode,
                )
                scenarios[mode] = plan
                forecasts[mode] = forecast

        chart = render_three_scenarios_chart(
            forecasts=forecasts,
            current_weight=current_weight,
            target_weight=target_weight,
        )
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🟢 Лайт", callback_data="goal_mode:light")],
                [InlineKeyboardButton(text="🟡 Медиум", callback_data="goal_mode:medium")],
                [InlineKeyboardButton(text="🔴 Хард", callback_data="goal_mode:hard")],
            ]
        )
        add_pending_photo(
            tid,
            PendingPhoto(
                content=chart.getvalue(),
                filename="weight_scenarios.png",
                caption="Сравнение режимов достижения цели. Выбери режим кнопками ниже.",
                keyboard=keyboard,
            ),
        )

        return {
            "ok": True,
            "current_weight_kg": round(current_weight, 2),
            "target_weight_kg": round(target_weight, 2),
            "direction": direction,
            "scenarios": scenarios,
            "graph_data": forecasts,
            "next_step": "Выбери режим: light / medium / hard",
        }

    async def select_weight_plan_mode(args: dict[str, Any]) -> dict[str, Any]:
        tid = int(args["telegram_id"])
        mode = str(args.get("mode", "medium"))
        if mode not in _MODES:
            return {"error": "mode must be one of light/medium/hard"}

        async with sessionmaker() as session:
            user = await crud.get_user(session, tid)
            if user is None:
                return {"error": "User not found. Сначала пройди /start."}
            if user.target_weight_kg is None:
                return {"error": "Сначала установи целевой вес через set_weight_goal."}
            target_weight = float(user.target_weight_kg)

            latest = await crud.get_latest_weight(session, tid)
            start_kg = float(latest.weight_kg if latest else user.weight_start_kg)
            now = datetime.now(tz=UTC)

            targets = calculate_plan_targets(
                current_weight=start_kg,
                target_weight=target_weight,
                gender=user.gender,
                age=user.age,
                height_cm=user.height_cm,
                activity_level=user.activity_level,
                mode=mode,
            )
            forecast = build_weight_forecast(
                current_weight=start_kg,
                target_weight=target_weight,
                gender=user.gender,
                age=user.age,
                height_cm=user.height_cm,
                activity_level=user.activity_level,
                mode=mode,
            )

            user.weight_plan_mode = mode
            user.weight_plan_start_date = now
            user.weight_plan_start_kg = start_kg
            user.daily_calories_target = float(targets["daily_calories"])
            user.daily_protein_target = float(targets["daily_protein"])
            user.daily_fat_target = float(targets["daily_fat"])
            user.daily_carbs_target = float(targets["daily_carbs"])
            await session.commit()

            actual_logs = await crud.get_weight_logs(session, tid, limit=90)

        actual_weights = [
            {
                "date": x.logged_at.astimezone(UTC).date().isoformat(),
                "weight_kg": float(x.weight_kg),
            }
            for x in reversed(actual_logs)
            if x.logged_at is not None
        ]
        chart = render_weight_plan_chart(
            forecast=forecast,
            actual_weights=actual_weights,
            target_weight=target_weight,
            mode=mode,
        )
        add_pending_photo(
            tid,
            PendingPhoto(
                content=chart.getvalue(),
                filename="weight_plan.png",
                caption=f"Твой персональный план ({mode}).",
            ),
        )

        return {
            "ok": True,
            "mode": mode,
            "plan_start_date": now.isoformat(),
            "plan_start_kg": round(start_kg, 2),
            "target_weight_kg": round(target_weight, 2),
            "daily_targets": targets,
            "forecast": forecast,
            "recommendations": (
                "Следи за ежедневной калорийностью, держи белок по плану и вноси вес минимум 3 раза в неделю."
            ),
        }

    async def get_weight_plan_status(args: dict[str, Any]) -> dict[str, Any]:
        tid = int(args["telegram_id"])
        async with sessionmaker() as session:
            user = await crud.get_user(session, tid)
            if user is None:
                return {"error": "User not found. Сначала пройди /start."}
            if (
                user.target_weight_kg is None
                or user.weight_plan_mode is None
                or user.weight_plan_start_date is None
                or user.weight_plan_start_kg is None
            ):
                return {"error": "Активный план не найден. Установи цель и выбери режим."}

            latest = await crud.get_latest_weight(session, tid)
            if latest is None:
                return {"error": "Нет замеров веса. Отправь вес через /weight."}

            now = datetime.now(tz=UTC)
            expected = get_expected_weight_for_date(
                plan_start_date=user.weight_plan_start_date,
                plan_start_kg=float(user.weight_plan_start_kg),
                target_weight=float(user.target_weight_kg),
                mode=user.weight_plan_mode,
                gender=user.gender,
                age=user.age,
                height_cm=user.height_cm,
                activity_level=user.activity_level,
                check_date=now,
            )
            actual = float(latest.weight_kg)
            compare = compare_progress(
                expected_kg=expected,
                actual_kg=actual,
                target_weight=float(user.target_weight_kg),
                current_weight=float(user.weight_plan_start_kg),
            )

            days_elapsed = max(0, (now.date() - user.weight_plan_start_date.date()).days)
            forecast = build_weight_forecast(
                current_weight=float(user.weight_plan_start_kg),
                target_weight=float(user.target_weight_kg),
                gender=user.gender,
                age=user.age,
                height_cm=user.height_cm,
                activity_level=user.activity_level,
                mode=user.weight_plan_mode,
            )
            days_remaining = max(0, len(forecast) * 7 - days_elapsed)

            total_distance = abs(float(user.weight_plan_start_kg) - float(user.target_weight_kg))
            done_distance = abs(float(user.weight_plan_start_kg) - actual)
            progress_pct = 100.0 if total_distance <= 0 else min(100.0, done_distance / total_distance * 100.0)

            return {
                "target": float(user.target_weight_kg),
                "mode": user.weight_plan_mode,
                "expected_today": round(expected, 2),
                "actual_latest": round(actual, 2),
                "deviation": compare["deviation_kg"],
                "on_track": compare["on_track"],
                "days_elapsed": days_elapsed,
                "days_remaining": int(days_remaining),
                "progress_pct": round(progress_pct, 1),
                "recommendation": compare["recommendation"],
            }

    async def get_weight_plan_forecast(args: dict[str, Any]) -> dict[str, Any]:
        tid = int(args["telegram_id"])
        async with sessionmaker() as session:
            user = await crud.get_user(session, tid)
            if user is None:
                return {"error": "User not found. Сначала пройди /start."}
            if user.target_weight_kg is None:
                return {"error": "Сначала установи целевой вес."}

            latest = await crud.get_latest_weight(session, tid)
            current_weight = float(latest.weight_kg if latest else user.weight_start_kg)
            mode = user.weight_plan_mode or "medium"
            forecast = build_weight_forecast(
                current_weight=current_weight,
                target_weight=float(user.target_weight_kg),
                gender=user.gender,
                age=user.age,
                height_cm=user.height_cm,
                activity_level=user.activity_level,
                mode=mode,
            )
            rows = await crud.get_weight_logs(session, tid, limit=120)

        actual_weights = [
            {
                "date": x.logged_at.astimezone(UTC).date().isoformat(),
                "weight_kg": float(x.weight_kg),
            }
            for x in reversed(rows)
            if x.logged_at is not None
        ]
        return {"forecast": forecast, "actual_weights": actual_weights}

    async def adjust_plan_targets(args: dict[str, Any]) -> dict[str, Any]:
        tid = int(args["telegram_id"])
        status = await get_weight_plan_status({"telegram_id": tid})
        if "error" in status:
            return status

        if bool(status["on_track"]):
            return {
                "ok": True,
                "updated": False,
                "message": "Ты идешь по плану, менять цели не нужно.",
                "daily_targets": None,
            }

        async with sessionmaker() as session:
            user = await crud.get_user(session, tid)
            if user is None or user.target_weight_kg is None:
                return {"error": "План не найден."}
            latest = await crud.get_latest_weight(session, tid)
            if latest is None:
                return {"error": "Нет замеров веса для корректировки плана."}

            current_mode = user.weight_plan_mode or "medium"
            mode_idx = list(_MODES).index(current_mode)
            next_mode = _MODES[min(mode_idx + 1, len(_MODES) - 1)]

            targets = calculate_plan_targets(
                current_weight=float(latest.weight_kg),
                target_weight=float(user.target_weight_kg),
                gender=user.gender,
                age=user.age,
                height_cm=user.height_cm,
                activity_level=user.activity_level,
                mode=next_mode,
            )

            user.weight_plan_mode = next_mode
            user.daily_calories_target = float(targets["daily_calories"])
            user.daily_protein_target = float(targets["daily_protein"])
            user.daily_fat_target = float(targets["daily_fat"])
            user.daily_carbs_target = float(targets["daily_carbs"])
            await session.commit()

        return {
            "ok": True,
            "updated": True,
            "new_mode": next_mode,
            "daily_targets": targets,
            "recommendation": (
                "План усилен на один шаг. Проверь сон, шаги и точность учета питания в ближайшие 7 дней."
            ),
        }

    async def get_exercise_recommendations(args: dict[str, Any]) -> dict[str, Any]:
        tid = int(args["telegram_id"])
        focus = str(args.get("focus", "general"))
        if focus not in {"cardio", "strength", "flexibility", "general"}:
            focus = "general"

        async with sessionmaker() as session:
            user = await crud.get_user(session, tid)
            if user is None:
                return {"error": "User not found. Сначала пройди /start."}
            latest = await crud.get_latest_weight(session, tid)

        current_weight = float(latest.weight_kg if latest else user.weight_start_kg)
        max_hr = max(80, 220 - int(user.age))
        fat_burn_zone = {"from": int(max_hr * 0.60), "to": int(max_hr * 0.70)}
        return {
            "focus": focus,
            "profile": {
                "gender": user.gender,
                "age": int(user.age),
                "height_cm": float(user.height_cm),
                "current_weight_kg": round(current_weight, 2),
                "activity_level": user.activity_level,
                "goal": user.goal,
                "target_weight_kg": user.target_weight_kg,
                "weight_plan_mode": user.weight_plan_mode,
            },
            "cardio_zone": fat_burn_zone,
            "constraints": {
                "high_weight_low_impact": current_weight >= 100,
                "beginner": user.activity_level in {"low", "light"},
            },
        }

    return {
        "set_weight_goal": set_weight_goal,
        "select_weight_plan_mode": select_weight_plan_mode,
        "get_weight_plan_status": get_weight_plan_status,
        "get_weight_plan_forecast": get_weight_plan_forecast,
        "adjust_plan_targets": adjust_plan_targets,
        "get_exercise_recommendations": get_exercise_recommendations,
    }
