from __future__ import annotations

from datetime import UTC, date, datetime, time, tzinfo
from typing import Any

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import GroupChat, GroupChatMember, MealLog, User, WeightLog


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
        session.add(user)
    else:
        for key, value in data.items():
            setattr(user, key, value)
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

