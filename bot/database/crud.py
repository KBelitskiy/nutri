from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta, tzinfo
from typing import Any

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import (
    Achievement,
    ConversationMessage,
    DailyCheckin,
    GroupChat,
    GroupChatMember,
    MealLog,
    MealTemplate,
    User,
    WaterLog,
    WeightLog,
)


def day_bounds(
    target_date: date | None = None,
    *,
    timezone: tzinfo = UTC,
) -> tuple[datetime, datetime]:
    d = target_date or datetime.now(tz=timezone).date()
    start_local = datetime.combine(d, time.min, tzinfo=timezone)
    end_local = datetime.combine(d, time.max, tzinfo=timezone)
    return start_local.astimezone(UTC), end_local.astimezone(UTC)


async def get_user(session: AsyncSession, telegram_id: int) -> User | None:
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    return result.scalar_one_or_none()


async def get_all_user_ids(session: AsyncSession) -> list[int]:
    result = await session.execute(select(User.telegram_id).order_by(User.telegram_id.asc()))
    return [int(x) for x in result.scalars().all()]


async def get_distinct_user_timezones(session: AsyncSession) -> list[str | None]:
    result = await session.execute(
        select(User.timezone).distinct()
    )
    return list(result.scalars().all())


async def get_user_ids_by_timezones(
    session: AsyncSession, timezone_names: list[str | None],
) -> list[int]:
    """Return user IDs whose timezone column matches any of the given values."""
    filters = []
    clean_names = [tz for tz in timezone_names if tz is not None]
    if clean_names:
        filters.append(User.timezone.in_(clean_names))
    if None in timezone_names:
        filters.append(User.timezone.is_(None))
    if not filters:
        return []
    from sqlalchemy import or_
    result = await session.execute(
        select(User.telegram_id).where(or_(*filters)).order_by(User.telegram_id.asc())
    )
    return [int(x) for x in result.scalars().all()]


async def get_users_by_ids(session: AsyncSession, telegram_ids: list[int]) -> list[User]:
    if not telegram_ids:
        return []
    result = await session.execute(select(User).where(User.telegram_id.in_(telegram_ids)))
    return list(result.scalars().all())


async def create_or_update_user(session: AsyncSession, data: dict[str, Any]) -> User:
    user = await get_user(session, int(data["telegram_id"]))
    if user is None:
        user = User(**data)
        if user.meal_reminder_times is None:
            user.meal_reminder_times = "9,13,19"
        if user.daily_water_target_ml is None:
            user.daily_water_target_ml = max(1200, int(float(user.weight_start_kg) * 30))
        session.add(user)
    else:
        for key, value in data.items():
            setattr(user, key, value)
        if user.daily_water_target_ml is None:
            user.daily_water_target_ml = max(1200, int(float(user.weight_start_kg) * 30))
        if user.meal_reminder_times is None:
            user.meal_reminder_times = "9,13,19"
    await session.commit()
    await session.refresh(user)
    return user


async def delete_user_data(session: AsyncSession, telegram_id: int) -> None:
    await session.execute(delete(User).where(User.telegram_id == telegram_id))
    await session.commit()


async def add_weight_log(session: AsyncSession, telegram_id: int, weight_kg: float) -> WeightLog:
    row = WeightLog(telegram_id=telegram_id, weight_kg=weight_kg)
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


async def get_latest_weight_at_or_before(
    session: AsyncSession, telegram_id: int, at_or_before: datetime
) -> WeightLog | None:
    result = await session.execute(
        select(WeightLog)
        .where(WeightLog.telegram_id == telegram_id, WeightLog.logged_at <= at_or_before)
        .order_by(WeightLog.logged_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_latest_weight(session: AsyncSession, telegram_id: int) -> WeightLog | None:
    result = await session.execute(
        select(WeightLog)
        .where(WeightLog.telegram_id == telegram_id)
        .order_by(WeightLog.logged_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def has_weight_log_today(
    session: AsyncSession,
    telegram_id: int,
    *,
    timezone: tzinfo = UTC,
) -> bool:
    start, end = day_bounds(timezone=timezone)
    result = await session.execute(
        select(func.count(WeightLog.id)).where(
            WeightLog.telegram_id == telegram_id,
            WeightLog.logged_at >= start,
            WeightLog.logged_at <= end,
        )
    )
    return int(result.scalar() or 0) > 0


async def get_weight_logs(session: AsyncSession, telegram_id: int, limit: int = 30) -> list[WeightLog]:
    result = await session.execute(
        select(WeightLog)
        .where(WeightLog.telegram_id == telegram_id)
        .order_by(WeightLog.logged_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_users_with_active_plan(session: AsyncSession) -> list[User]:
    result = await session.execute(
        select(User)
        .where(User.weight_plan_mode.is_not(None), User.target_weight_kg.is_not(None))
        .order_by(User.telegram_id.asc())
    )
    return list(result.scalars().all())


async def add_meal_log(
    session: AsyncSession,
    telegram_id: int,
    description: str,
    calories: float,
    protein_g: float,
    fat_g: float,
    carbs_g: float,
    photo_file_id: str | None = None,
    meal_type: str = "snack",
) -> MealLog:
    row = MealLog(
        telegram_id=telegram_id,
        description=description,
        calories=calories,
        protein_g=protein_g,
        fat_g=fat_g,
        carbs_g=carbs_g,
        photo_file_id=photo_file_id,
        meal_type=meal_type,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


async def has_meals_in_last_hours(
    session: AsyncSession,
    telegram_id: int,
    *,
    hours: int = 2,
    now: datetime | None = None,
) -> bool:
    anchor = now or datetime.now(tz=UTC)
    cutoff = anchor - timedelta(hours=max(1, hours))
    result = await session.execute(
        select(func.count(MealLog.id)).where(
            MealLog.telegram_id == telegram_id,
            MealLog.logged_at >= cutoff,
            MealLog.logged_at <= anchor,
        )
    )
    return int(result.scalar() or 0) > 0


async def update_meal_log(session: AsyncSession, telegram_id: int, meal_id: int, fields: dict[str, Any]) -> bool:
    q = (
        update(MealLog)
        .where(MealLog.id == meal_id, MealLog.telegram_id == telegram_id)
        .values(**fields)
    )
    result = await session.execute(q)
    await session.commit()
    return result.rowcount > 0


async def delete_meal_log(session: AsyncSession, telegram_id: int, meal_id: int) -> bool:
    result = await session.execute(
        delete(MealLog).where(MealLog.id == meal_id, MealLog.telegram_id == telegram_id)
    )
    await session.commit()
    return result.rowcount > 0


async def get_meals_for_day(
    session: AsyncSession,
    telegram_id: int,
    target_date: date | None = None,
    *,
    timezone: tzinfo = UTC,
) -> list[MealLog]:
    start, end = day_bounds(target_date, timezone=timezone)
    result = await session.execute(
        select(MealLog)
        .where(MealLog.telegram_id == telegram_id, MealLog.logged_at >= start, MealLog.logged_at <= end)
        .order_by(MealLog.logged_at.asc())
    )
    return list(result.scalars().all())


async def get_meals_for_period(
    session: AsyncSession, telegram_id: int, start: datetime, end: datetime
) -> list[MealLog]:
    result = await session.execute(
        select(MealLog)
        .where(MealLog.telegram_id == telegram_id, MealLog.logged_at >= start, MealLog.logged_at <= end)
        .order_by(MealLog.logged_at.asc())
    )
    return list(result.scalars().all())


async def get_meal_summary_for_day(
    session: AsyncSession,
    telegram_id: int,
    target_date: date | None = None,
    *,
    timezone: tzinfo = UTC,
) -> dict[str, float]:
    start, end = day_bounds(target_date, timezone=timezone)
    result = await session.execute(
        select(
            func.coalesce(func.sum(MealLog.calories), 0.0),
            func.coalesce(func.sum(MealLog.protein_g), 0.0),
            func.coalesce(func.sum(MealLog.fat_g), 0.0),
            func.coalesce(func.sum(MealLog.carbs_g), 0.0),
        ).where(MealLog.telegram_id == telegram_id, MealLog.logged_at >= start, MealLog.logged_at <= end)
    )
    calories, protein, fat, carbs = result.one()
    return {
        "calories": float(calories or 0.0),
        "protein_g": float(protein or 0.0),
        "fat_g": float(fat or 0.0),
        "carbs_g": float(carbs or 0.0),
    }


async def get_meal_summary_for_period(
    session: AsyncSession, telegram_id: int, start: datetime, end: datetime
) -> dict[str, float]:
    result = await session.execute(
        select(
            func.coalesce(func.sum(MealLog.calories), 0.0),
            func.coalesce(func.sum(MealLog.protein_g), 0.0),
            func.coalesce(func.sum(MealLog.fat_g), 0.0),
            func.coalesce(func.sum(MealLog.carbs_g), 0.0),
        ).where(MealLog.telegram_id == telegram_id, MealLog.logged_at >= start, MealLog.logged_at <= end)
    )
    calories, protein, fat, carbs = result.one()
    return {
        "calories": float(calories or 0.0),
        "protein_g": float(protein or 0.0),
        "fat_g": float(fat or 0.0),
        "carbs_g": float(carbs or 0.0),
    }


async def get_meal_stats(
    session: AsyncSession, telegram_id: int, start: datetime, end: datetime
) -> dict[str, float]:
    result = await session.execute(
        select(
            func.coalesce(func.avg(MealLog.calories), 0.0),
            func.coalesce(func.avg(MealLog.protein_g), 0.0),
            func.coalesce(func.avg(MealLog.fat_g), 0.0),
            func.coalesce(func.avg(MealLog.carbs_g), 0.0),
            func.count(MealLog.id),
        ).where(MealLog.telegram_id == telegram_id, MealLog.logged_at >= start, MealLog.logged_at <= end)
    )
    avg_cal, avg_p, avg_f, avg_c, count = result.one()
    return {
        "avg_calories": float(avg_cal or 0.0),
        "avg_protein_g": float(avg_p or 0.0),
        "avg_fat_g": float(avg_f or 0.0),
        "avg_carbs_g": float(avg_c or 0.0),
        "meals_count": float(count or 0),
    }


async def get_daily_avg_stats(
    session: AsyncSession,
    telegram_id: int,
    start: datetime,
    end: datetime,
    *,
    timezone: tzinfo = UTC,
) -> dict[str, float]:
    meals = await get_meals_for_period(session, telegram_id, start, end)
    if not meals:
        return {
            "avg_calories": 0.0,
            "avg_protein_g": 0.0,
            "avg_fat_g": 0.0,
            "avg_carbs_g": 0.0,
            "meals_count": 0.0,
            "days_with_data": 0.0,
        }

    daily: dict[date, dict[str, float]] = {}
    for meal in meals:
        if meal.logged_at is None:
            continue
        day_key = meal.logged_at.astimezone(timezone).date()
        if day_key not in daily:
            daily[day_key] = {
                "calories": 0.0,
                "protein_g": 0.0,
                "fat_g": 0.0,
                "carbs_g": 0.0,
            }
        daily[day_key]["calories"] += float(meal.calories)
        daily[day_key]["protein_g"] += float(meal.protein_g)
        daily[day_key]["fat_g"] += float(meal.fat_g)
        daily[day_key]["carbs_g"] += float(meal.carbs_g)

    days_count = max(1, len(daily))
    sum_calories = sum(row["calories"] for row in daily.values())
    sum_protein = sum(row["protein_g"] for row in daily.values())
    sum_fat = sum(row["fat_g"] for row in daily.values())
    sum_carbs = sum(row["carbs_g"] for row in daily.values())
    return {
        "avg_calories": sum_calories / days_count,
        "avg_protein_g": sum_protein / days_count,
        "avg_fat_g": sum_fat / days_count,
        "avg_carbs_g": sum_carbs / days_count,
        "meals_count": float(len(meals)),
        "days_with_data": float(len(daily)),
    }


async def add_water_log(session: AsyncSession, telegram_id: int, amount_ml: int) -> WaterLog:
    row = WaterLog(telegram_id=telegram_id, amount_ml=amount_ml)
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


async def get_water_summary_for_day(
    session: AsyncSession,
    telegram_id: int,
    target_date: date | None = None,
    *,
    timezone: tzinfo = UTC,
) -> int:
    start, end = day_bounds(target_date, timezone=timezone)
    result = await session.execute(
        select(func.coalesce(func.sum(WaterLog.amount_ml), 0)).where(
            WaterLog.telegram_id == telegram_id,
            WaterLog.logged_at >= start,
            WaterLog.logged_at <= end,
        )
    )
    return int(result.scalar() or 0)


async def create_meal_template(
    session: AsyncSession,
    telegram_id: int,
    name: str,
    description: str,
    calories: float,
    protein_g: float,
    fat_g: float,
    carbs_g: float,
    meal_type: str = "snack",
) -> MealTemplate:
    row = MealTemplate(
        telegram_id=telegram_id,
        name=name,
        description=description,
        calories=calories,
        protein_g=protein_g,
        fat_g=fat_g,
        carbs_g=carbs_g,
        meal_type=meal_type,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


async def get_meal_templates(session: AsyncSession, telegram_id: int) -> list[MealTemplate]:
    result = await session.execute(
        select(MealTemplate)
        .where(MealTemplate.telegram_id == telegram_id)
        .order_by(MealTemplate.use_count.desc(), MealTemplate.created_at.desc())
    )
    return list(result.scalars().all())


async def get_meal_template_by_id(
    session: AsyncSession, telegram_id: int, template_id: int
) -> MealTemplate | None:
    result = await session.execute(
        select(MealTemplate).where(
            MealTemplate.id == template_id,
            MealTemplate.telegram_id == telegram_id,
        )
    )
    return result.scalar_one_or_none()


async def increment_meal_template_usage(
    session: AsyncSession, telegram_id: int, template_id: int
) -> bool:
    result = await session.execute(
        update(MealTemplate)
        .where(MealTemplate.id == template_id, MealTemplate.telegram_id == telegram_id)
        .values(use_count=MealTemplate.use_count + 1)
    )
    await session.commit()
    return result.rowcount > 0


async def delete_meal_template(session: AsyncSession, telegram_id: int, template_id: int) -> bool:
    result = await session.execute(
        delete(MealTemplate).where(
            MealTemplate.id == template_id,
            MealTemplate.telegram_id == telegram_id,
        )
    )
    await session.commit()
    return result.rowcount > 0


async def add_conversation_message(
    session: AsyncSession, telegram_id: int, role: str, content: str
) -> ConversationMessage:
    row = ConversationMessage(telegram_id=telegram_id, role=role, content=content)
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


async def get_recent_conversation(
    session: AsyncSession,
    telegram_id: int,
    limit: int = 10,
) -> list[tuple[str, str]]:
    result = await session.execute(
        select(ConversationMessage)
        .where(ConversationMessage.telegram_id == telegram_id)
        .order_by(ConversationMessage.created_at.desc(), ConversationMessage.id.desc())
        .limit(max(2, limit * 2))
    )
    rows = list(result.scalars().all())
    rows.reverse()
    pairs: list[tuple[str, str]] = []
    pending_user: str | None = None
    for row in rows:
        if row.role == "user":
            pending_user = row.content
            continue
        if row.role == "assistant" and pending_user is not None:
            pairs.append((pending_user, row.content))
            pending_user = None
    return pairs[-limit:]


async def clear_old_conversation(
    session: AsyncSession,
    telegram_id: int,
    keep_pairs: int = 10,
) -> int:
    result = await session.execute(
        select(ConversationMessage.id)
        .where(ConversationMessage.telegram_id == telegram_id)
        .order_by(ConversationMessage.created_at.desc(), ConversationMessage.id.desc())
    )
    ids = list(result.scalars().all())
    keep = max(2, keep_pairs * 2)
    to_delete = ids[keep:]
    if not to_delete:
        return 0
    del_result = await session.execute(
        delete(ConversationMessage).where(ConversationMessage.id.in_(to_delete))
    )
    await session.commit()
    return int(del_result.rowcount or 0)


async def get_daily_checkin(
    session: AsyncSession, telegram_id: int, checkin_date: date
) -> DailyCheckin | None:
    result = await session.execute(
        select(DailyCheckin).where(
            DailyCheckin.telegram_id == telegram_id,
            DailyCheckin.checkin_date == checkin_date,
        )
    )
    return result.scalar_one_or_none()


async def upsert_daily_checkin(
    session: AsyncSession,
    telegram_id: int,
    checkin_date: date,
    *,
    calories_ok: bool,
    protein_ok: bool,
    logged_meals: int,
) -> DailyCheckin:
    row = await get_daily_checkin(session, telegram_id, checkin_date)
    if row is None:
        row = DailyCheckin(
            telegram_id=telegram_id,
            checkin_date=checkin_date,
            calories_ok=calories_ok,
            protein_ok=protein_ok,
            logged_meals=logged_meals,
        )
        session.add(row)
    else:
        row.calories_ok = calories_ok
        row.protein_ok = protein_ok
        row.logged_meals = logged_meals
    await session.commit()
    await session.refresh(row)
    return row


async def get_recent_calorie_streak(
    session: AsyncSession,
    telegram_id: int,
    *,
    as_of: date | None = None,
    max_days: int = 365,
) -> int:
    anchor = as_of or datetime.now(tz=UTC).date()
    result = await session.execute(
        select(DailyCheckin)
        .where(
            DailyCheckin.telegram_id == telegram_id,
            DailyCheckin.checkin_date <= anchor,
        )
        .order_by(DailyCheckin.checkin_date.desc())
        .limit(max_days)
    )
    rows = list(result.scalars().all())
    day_map = {row.checkin_date: bool(row.calories_ok) for row in rows}
    streak = 0
    cursor = anchor
    while day_map.get(cursor, False):
        streak += 1
        cursor = cursor.fromordinal(cursor.toordinal() - 1)
    return streak


async def has_achievement_badge(session: AsyncSession, telegram_id: int, badge_key: str) -> bool:
    result = await session.execute(
        select(func.count(Achievement.id)).where(
            Achievement.telegram_id == telegram_id,
            Achievement.badge_key == badge_key,
        )
    )
    return int(result.scalar() or 0) > 0


async def add_achievement(session: AsyncSession, telegram_id: int, badge_key: str) -> Achievement:
    row = Achievement(telegram_id=telegram_id, badge_key=badge_key)
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


async def get_user_achievements(session: AsyncSession, telegram_id: int) -> list[Achievement]:
    result = await session.execute(
        select(Achievement)
        .where(Achievement.telegram_id == telegram_id)
        .order_by(Achievement.earned_at.desc())
    )
    return list(result.scalars().all())


async def get_weekly_coaching_data(
    session: AsyncSession,
    telegram_id: int,
    *,
    days: int = 7,
    timezone: tzinfo = UTC,
) -> dict[str, Any]:
    user = await get_user(session, telegram_id)
    if user is None:
        return {"error": "User not found"}
    end = datetime.now(tz=UTC)
    start = end - timedelta(days=max(1, days))
    meals = await get_meals_for_period(session, telegram_id, start, end)
    weights = await get_weight_logs(session, telegram_id, limit=max(14, days * 2))

    daily_map: dict[str, dict[str, float]] = {}
    for meal in meals:
        if meal.logged_at is None:
            continue
        day_key = meal.logged_at.astimezone(timezone).date().isoformat()
        if day_key not in daily_map:
            daily_map[day_key] = {
                "calories": 0.0,
                "protein_g": 0.0,
                "fat_g": 0.0,
                "carbs_g": 0.0,
                "meals_count": 0.0,
            }
        daily_map[day_key]["calories"] += float(meal.calories)
        daily_map[day_key]["protein_g"] += float(meal.protein_g)
        daily_map[day_key]["fat_g"] += float(meal.fat_g)
        daily_map[day_key]["carbs_g"] += float(meal.carbs_g)
        daily_map[day_key]["meals_count"] += 1.0

    daily_totals = [
        {
            "date": day,
            "calories": round(values["calories"], 1),
            "protein_g": round(values["protein_g"], 1),
            "fat_g": round(values["fat_g"], 1),
            "carbs_g": round(values["carbs_g"], 1),
            "meals_count": int(values["meals_count"]),
        }
        for day, values in sorted(daily_map.items())
    ]
    weight_history = [
        {
            "date": row.logged_at.astimezone(timezone).date().isoformat() if row.logged_at else None,
            "weight_kg": float(row.weight_kg),
        }
        for row in reversed(weights)
        if row.logged_at is not None
    ]
    return {
        "profile": {
            "gender": user.gender,
            "age": user.age,
            "height_cm": user.height_cm,
            "activity_level": user.activity_level,
            "goal": user.goal,
            "daily_calories_target": user.daily_calories_target,
            "daily_protein_target": user.daily_protein_target,
            "daily_fat_target": user.daily_fat_target,
            "daily_carbs_target": user.daily_carbs_target,
        },
        "daily_totals": daily_totals,
        "weight_history": weight_history,
    }


async def add_group_chat(session: AsyncSession, chat_id: int, title: str | None = None) -> GroupChat:
    chat = await session.get(GroupChat, chat_id)
    if chat is None:
        chat = GroupChat(chat_id=chat_id, title=title)
        session.add(chat)
    else:
        chat.title = title
    await session.commit()
    await session.refresh(chat)
    return chat


async def remove_group_chat(session: AsyncSession, chat_id: int) -> None:
    await session.execute(delete(GroupChat).where(GroupChat.chat_id == chat_id))
    await session.commit()


async def get_group_chats(session: AsyncSession) -> list[GroupChat]:
    result = await session.execute(select(GroupChat).order_by(GroupChat.chat_id.asc()))
    return list(result.scalars().all())


async def ensure_group_member(
    session: AsyncSession, chat_id: int, telegram_id: int
) -> GroupChatMember:
    row = await session.get(GroupChatMember, {"chat_id": chat_id, "telegram_id": telegram_id})
    if row is None:
        row = GroupChatMember(chat_id=chat_id, telegram_id=telegram_id)
        session.add(row)
        await session.commit()
        await session.refresh(row)
    return row


async def get_chat_member_user_ids(session: AsyncSession, chat_id: int) -> list[int]:
    result = await session.execute(
        select(GroupChatMember.telegram_id)
        .where(GroupChatMember.chat_id == chat_id)
        .order_by(GroupChatMember.telegram_id.asc())
    )
    return list(result.scalars().all())

