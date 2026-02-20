from __future__ import annotations

from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.database import crud
from bot.keyboards import BTN_WATER_QUICK
from bot.runtime import get_app_context

router = Router()


def _parse_amount_ml(text: str) -> int | None:
    parts = text.split(maxsplit=1)
    if len(parts) != 2:
        return None
    raw = parts[1].strip().replace("мл", "").replace("ml", "").strip()
    if not raw:
        return None
    if not raw.isdigit():
        return None
    value = int(raw)
    if value < 50 or value > 3000:
        return None
    return value


def _user_tz_or_default(tz_name: str | None, fallback_tz: str) -> ZoneInfo:
    try:
        return ZoneInfo(tz_name or fallback_tz)
    except Exception:  # noqa: BLE001
        return ZoneInfo(fallback_tz)


@router.message(F.text == BTN_WATER_QUICK)
async def water_quick_add(message: Message) -> None:
    if not message.from_user:
        return
    ctx = get_app_context()
    async with ctx.sessionmaker() as session:
        user = await crud.get_user(session, message.from_user.id)
        if user is None:
            await message.answer("Сначала пройди /start.")
            return
        if user.daily_water_target_ml is None:
            user.daily_water_target_ml = max(1200, int(float(user.weight_start_kg) * 30))
            await session.commit()
        tz = _user_tz_or_default(user.timezone, ctx.settings.league_report_timezone)
        await crud.add_water_log(session, message.from_user.id, 250)
        total_ml = await crud.get_water_summary_for_day(
            session,
            message.from_user.id,
            timezone=tz,
        )
        target_ml = int(user.daily_water_target_ml or 2000)
    pct = round((total_ml / target_ml * 100.0), 1) if target_ml > 0 else 0.0
    await message.answer(
        f"Добавил 250 мл воды.\n"
        f"Сегодня: {total_ml}/{target_ml} мл ({pct}%), осталось {max(0, target_ml - total_ml)} мл."
    )


@router.message(Command("water"))
async def water_command(message: Message) -> None:
    if not message.from_user:
        return
    ctx = get_app_context()
    amount = _parse_amount_ml(message.text or "")
    async with ctx.sessionmaker() as session:
        user = await crud.get_user(session, message.from_user.id)
        if user is None:
            await message.answer("Сначала пройди /start.")
            return
        if user.daily_water_target_ml is None:
            user.daily_water_target_ml = max(1200, int(float(user.weight_start_kg) * 30))
            await session.commit()
        tz = _user_tz_or_default(user.timezone, ctx.settings.league_report_timezone)
        if amount is not None:
            await crud.add_water_log(session, message.from_user.id, amount)
        total_ml = await crud.get_water_summary_for_day(
            session,
            message.from_user.id,
            timezone=tz,
        )
        target_ml = int(user.daily_water_target_ml or 2000)
    pct = round((total_ml / target_ml * 100.0), 1) if target_ml > 0 else 0.0
    if amount is None:
        await message.answer(
            f"Вода за сегодня: {total_ml}/{target_ml} мл ({pct}%).\n"
            f"Осталось: {max(0, target_ml - total_ml)} мл.\n"
            f"Чтобы добавить воду, используй /water 300 или кнопку «{BTN_WATER_QUICK}»."
        )
        return
    await message.answer(
        f"Записал {amount} мл воды.\n"
        f"Сегодня: {total_ml}/{target_ml} мл ({pct}%), осталось {max(0, target_ml - total_ml)} мл."
    )
