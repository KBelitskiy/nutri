from __future__ import annotations

from datetime import UTC, datetime

from aiogram import Router
from aiogram.types import BufferedInputFile

from bot.database import crud
from bot.runtime import get_app_context
from bot.services.chart import render_weight_plan_chart
from bot.services.weight_plan import build_weight_forecast, calculate_plan_targets

router = Router()


@router.callback_query(lambda c: c.data and c.data.startswith("goal_mode:"))
async def goal_mode_selected(callback) -> None:  # type: ignore[no-untyped-def]
    if not callback.from_user:
        await callback.answer()
        return

    mode = str(callback.data.split(":", 1)[1]).strip().lower()
    if mode not in {"light", "medium", "hard"}:
        await callback.answer("Неизвестный режим", show_alert=True)
        return

    ctx = get_app_context()
    user_id = callback.from_user.id
    async with ctx.sessionmaker() as session:
        user = await crud.get_user(session, user_id)
        if user is None:
            await callback.answer("Сначала пройди /start", show_alert=True)
            return
        if user.target_weight_kg is None:
            await callback.answer("Сначала установи цель по весу", show_alert=True)
            return

        latest = await crud.get_latest_weight(session, user_id)
        start_kg = float(latest.weight_kg if latest else user.weight_start_kg)
        now = datetime.now(tz=UTC)

        targets = calculate_plan_targets(
            current_weight=start_kg,
            target_weight=float(user.target_weight_kg),
            gender=user.gender,
            age=user.age,
            height_cm=user.height_cm,
            activity_level=user.activity_level,
            mode=mode,
        )
        forecast = build_weight_forecast(
            current_weight=start_kg,
            target_weight=float(user.target_weight_kg),
            gender=user.gender,
            age=user.age,
            height_cm=user.height_cm,
            activity_level=user.activity_level,
            mode=mode,
        )
        logs = await crud.get_weight_logs(session, user_id, limit=90)
        target_weight = float(user.target_weight_kg)

        user.weight_plan_mode = mode
        user.weight_plan_start_date = now
        user.weight_plan_start_kg = start_kg
        user.daily_calories_target = float(targets["daily_calories"])
        user.daily_protein_target = float(targets["daily_protein"])
        user.daily_fat_target = float(targets["daily_fat"])
        user.daily_carbs_target = float(targets["daily_carbs"])
        await session.commit()

    actual_weights = [
        {
            "date": x.logged_at.astimezone(UTC).date().isoformat(),
            "weight_kg": float(x.weight_kg),
        }
        for x in reversed(logs)
        if x.logged_at is not None
    ]
    chart = render_weight_plan_chart(
        forecast=forecast,
        actual_weights=actual_weights,
        target_weight=target_weight,
        mode=mode,
    )

    caption = (
        f"Режим <b>{mode}</b> сохранен.\n"
        f"Цели: {targets['daily_calories']:.0f} ккал | "
        f"Б {targets['daily_protein']:.1f} г | "
        f"Ж {targets['daily_fat']:.1f} г | "
        f"У {targets['daily_carbs']:.1f} г.\n"
        f"Оценочный срок: {targets['estimated_weeks']} нед."
    )
    await callback.answer("Режим сохранен")
    if callback.message:
        await callback.message.answer_photo(
            BufferedInputFile(chart.getvalue(), filename="weight_plan.png"),
            caption=caption,
            parse_mode="HTML",
        )
