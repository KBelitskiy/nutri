from __future__ import annotations

from datetime import UTC, datetime

from bot.database import crud
from bot.services.league_reports import build_daily_league_report, build_weekly_league_report


async def test_build_daily_league_report_contains_leagues_and_metrics(sessionmaker) -> None:
    user_data = {
        "telegram_id": 111,
        "username": "daily_user",
        "gender": "female",
        "age": 28,
        "height_cm": 168.0,
        "weight_start_kg": 70.0,
        "activity_level": "moderate",
        "goal": "lose",
        "daily_calories_target": 2000.0,
        "daily_protein_target": 100.0,
        "daily_fat_target": 60.0,
        "daily_carbs_target": 220.0,
    }
    async with sessionmaker() as session:
        await crud.create_or_update_user(session, user_data)
        await crud.add_group_chat(session, -100500, "League Chat")
        await crud.ensure_group_member(session, -100500, 111)
        meal = await crud.add_meal_log(session, 111, "meal", 1000.0, 30.0, 20.0, 90.0)
        w1 = await crud.add_weight_log(session, 111, 70.0)
        w2 = await crud.add_weight_log(session, 111, 69.5)

        now = datetime.now(tz=UTC)
        meal.logged_at = now
        w1.logged_at = now.replace(hour=8, minute=0, second=0, microsecond=0)
        w2.logged_at = now.replace(hour=20, minute=0, second=0, microsecond=0)
        await session.commit()

        report = await build_daily_league_report(session, -100500, "UTC")

    assert report is not None
    assert "Лига: Похудание" in report
    assert "@daily_user" in report
    assert "50.0% калорий" in report


async def test_build_weekly_league_report_contains_weekly_goal_pct(sessionmaker) -> None:
    user_data = {
        "telegram_id": 222,
        "username": "weekly_user",
        "gender": "male",
        "age": 34,
        "height_cm": 181.0,
        "weight_start_kg": 86.0,
        "activity_level": "moderate",
        "goal": "maintain",
        "daily_calories_target": 2000.0,
        "daily_protein_target": 120.0,
        "daily_fat_target": 70.0,
        "daily_carbs_target": 230.0,
    }
    async with sessionmaker() as session:
        await crud.create_or_update_user(session, user_data)
        await crud.add_group_chat(session, -100600, "League Chat")
        await crud.ensure_group_member(session, -100600, 222)
        meal = await crud.add_meal_log(session, 222, "meal", 7000.0, 200.0, 100.0, 800.0)
        w1 = await crud.add_weight_log(session, 222, 86.0)
        w2 = await crud.add_weight_log(session, 222, 85.2)

        now = datetime.now(tz=UTC)
        meal.logged_at = now
        w1.logged_at = now.replace(day=max(1, now.day - 6), hour=8, minute=0, second=0, microsecond=0)
        w2.logged_at = now
        await session.commit()

        report = await build_weekly_league_report(session, -100600, "UTC")

    assert report is not None
    assert "Лига: Удержание" in report
    assert "@weekly_user" in report
    assert "50.0% недельной цели" in report
