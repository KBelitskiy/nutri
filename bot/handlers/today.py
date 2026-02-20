from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, or_f
from aiogram.types import Message
from zoneinfo import ZoneInfo

from bot.database import crud
from bot.handlers.utils import today_with_meals_text
from bot.keyboards import BTN_TODAY
from bot.runtime import get_app_context

router = Router()


@router.message(or_f(Command("today"), F.text == BTN_TODAY))
async def today(message: Message) -> None:
    if not message.from_user:
        return
    ctx = get_app_context()
    async with ctx.sessionmaker() as session:
        user = await crud.get_user(session, message.from_user.id)
        if user is None:
            await message.answer("Сначала пройди /start")
            return
        tz_name = user.timezone or ctx.settings.league_report_timezone
        tz = ZoneInfo(tz_name)
        consumed = await crud.get_meal_summary_for_day(
            session, message.from_user.id, timezone=tz
        )
        meals = await crud.get_meals_for_day(session, message.from_user.id, timezone=tz)
        water_today_ml = await crud.get_water_summary_for_day(
            session,
            message.from_user.id,
            timezone=tz,
        )
        streak_days = await crud.get_recent_calorie_streak(session, message.from_user.id)

    await message.answer(
        today_with_meals_text(
            meals,
            consumed,
            user,
            water_today_ml=water_today_ml,
            streak_days=streak_days,
        )
    )

