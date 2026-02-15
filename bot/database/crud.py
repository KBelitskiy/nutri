from __future__ import annotations

from datetime import UTC, date, datetime, time
from typing import Any

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import MealLog, User, WeightLog


def day_bounds(target_date: date | None = None) -> tuple[datetime, datetime]:
    d = target_date or datetime.now(tz=UTC).date()
    start = datetime.combine(d, time.min, tzinfo=UTC)
    end = datetime.combine(d, time.max, tzinfo=UTC)
    return start, end


async def get_user(session: AsyncSession, telegram_id: int) -> User | None:
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    return result.scalar_one_or_none()


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


async def get_weight_logs(session: AsyncSession, telegram_id: int, limit: int = 30) -> list[WeightLog]:
    result = await session.execute(
        select(WeightLog)
        .where(WeightLog.telegram_id == telegram_id)
        .order_by(WeightLog.logged_at.desc())
        .limit(limit)
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
    session: AsyncSession, telegram_id: int, target_date: date | None = None
) -> list[MealLog]:
    start, end = day_bounds(target_date)
    result = await session.execute(
        select(MealLog)
        .where(MealLog.telegram_id == telegram_id, MealLog.logged_at >= start, MealLog.logged_at <= end)
        .order_by(MealLog.logged_at.asc())
    )
    return list(result.scalars().all())


async def get_meal_summary_for_day(
    session: AsyncSession, telegram_id: int, target_date: date | None = None
) -> dict[str, float]:
    start, end = day_bounds(target_date)
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

