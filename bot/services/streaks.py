from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from bot.database import crud

BADGE_MILESTONES = (3, 7, 14, 30, 60, 90)


async def evaluate_daily_streak_for_user(
    session: AsyncSession,
    telegram_id: int,
    *,
    timezone: ZoneInfo,
    target_date: date | None = None,
) -> dict[str, object]:
    user = await crud.get_user(session, telegram_id)
    if user is None:
        return {"error": "User not found"}

    consumed = await crud.get_meal_summary_for_day(
        session,
        telegram_id,
        target_date=target_date,
        timezone=timezone,
    )
    meals = await crud.get_meals_for_day(
        session,
        telegram_id,
        target_date=target_date,
        timezone=timezone,
    )
    checkin_day = target_date or datetime.now(tz=timezone).date()
    cal_target = float(user.daily_calories_target or 0.0)
    protein_target = float(user.daily_protein_target or 0.0)
    calories = float(consumed.get("calories", 0.0))
    protein = float(consumed.get("protein_g", 0.0))

    calories_ok = False
    if cal_target > 0:
        lower = cal_target * 0.9
        upper = cal_target * 1.1
        calories_ok = lower <= calories <= upper
    protein_ok = protein_target > 0 and protein >= protein_target * 0.9

    await crud.upsert_daily_checkin(
        session,
        telegram_id,
        checkin_day,
        calories_ok=calories_ok,
        protein_ok=protein_ok,
        logged_meals=len(meals),
    )
    streak_days = await crud.get_recent_calorie_streak(session, telegram_id, as_of=checkin_day)

    new_badges: list[str] = []
    for milestone in BADGE_MILESTONES:
        if streak_days < milestone:
            continue
        badge_key = f"streak_{milestone}"
        if await crud.has_achievement_badge(session, telegram_id, badge_key):
            continue
        await crud.add_achievement(session, telegram_id, badge_key)
        new_badges.append(badge_key)

    return {
        "telegram_id": telegram_id,
        "checkin_date": checkin_day.isoformat(),
        "calories_ok": calories_ok,
        "protein_ok": protein_ok,
        "streak_days": streak_days,
        "new_badges": new_badges,
    }


async def get_streak_info(session: AsyncSession, telegram_id: int) -> dict[str, object]:
    streak_days = await crud.get_recent_calorie_streak(session, telegram_id)
    badges = await crud.get_user_achievements(session, telegram_id)
    return {
        "streak_days": streak_days,
        "badges": [x.badge_key for x in badges],
    }
