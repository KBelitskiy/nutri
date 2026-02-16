from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.filters import Command, or_f
from aiogram.types import Message

from bot.database import crud
from bot.keyboards import BTN_STATS
from bot.runtime import get_app_context

router = Router()


@router.message(or_f(Command("stats"), F.text == BTN_STATS))
async def stats(message: Message) -> None:
    if not message.from_user:
        return
    text = message.text or ""
    period = "week"
    parts = text.split(maxsplit=1)
    if len(parts) == 2 and parts[1] in {"day", "week", "month"}:
        period = parts[1]

    ctx = get_app_context()
    tz = ZoneInfo(ctx.settings.league_report_timezone)
    now_local = datetime.now(tz=tz)
    now = now_local.astimezone(UTC)
    if period == "day":
        start, end = crud.day_bounds(timezone=tz)
    elif period == "month":
        start = now - timedelta(days=30)
        end = now
    else:
        start = now - timedelta(days=7)
        end = now

    async with ctx.sessionmaker() as session:
        user = await crud.get_user(session, message.from_user.id)
        if user is None:
            await message.answer("Сначала пройди /start.")
            return
        stats_data = await crud.get_meal_stats(session, message.from_user.id, start, end)

    meals_count = int(stats_data["meals_count"])
    if meals_count == 0:
        await message.answer(f"За период `{period}` нет данных по приемам пищи.")
        return

    def pct(value: float, target: float) -> float:
        return round((value / target) * 100.0, 1) if target else 0.0

    await message.answer(
        f"Статистика за {period}:\n"
        f"Средние калории: {stats_data['avg_calories']:.1f} "
        f"({pct(stats_data['avg_calories'], user.daily_calories_target)}% цели)\n"
        f"Средний белок: {stats_data['avg_protein_g']:.1f} г "
        f"({pct(stats_data['avg_protein_g'], user.daily_protein_target)}% цели)\n"
        f"Средний жир: {stats_data['avg_fat_g']:.1f} г "
        f"({pct(stats_data['avg_fat_g'], user.daily_fat_target)}% цели)\n"
        f"Средние углеводы: {stats_data['avg_carbs_g']:.1f} г "
        f"({pct(stats_data['avg_carbs_g'], user.daily_carbs_target)}% цели)\n"
        f"Логов еды: {meals_count}"
    )

