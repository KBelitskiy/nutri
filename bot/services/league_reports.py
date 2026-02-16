from __future__ import annotations

from collections import defaultdict
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from bot.database import crud
from bot.database.models import User

GOAL_LABELS = {
    "lose": "Похудание",
    "maintain": "Удержание",
    "gain": "Набор веса",
}
GOAL_ORDER = ("lose", "maintain", "gain")


def _day_bounds_utc(target_date: date, tz: ZoneInfo) -> tuple[datetime, datetime]:
    start_local = datetime.combine(target_date, time.min, tzinfo=tz)
    end_local = datetime.combine(target_date, time.max, tzinfo=tz)
    return start_local.astimezone(UTC), end_local.astimezone(UTC)


def _user_display_name(user: User) -> str:
    if user.username:
        return f"@{user.username}"
    return f"ID {user.telegram_id}"


def _pct(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return round((numerator / denominator) * 100, 1)


def _weight_delta_pct(today_weight: float | None, prev_weight: float | None) -> str:
    if today_weight is None or prev_weight is None or prev_weight <= 0:
        return "—"
    delta = ((today_weight - prev_weight) / prev_weight) * 100
    return f"{delta:+.2f}%"


async def _users_for_chat(session: AsyncSession, chat_id: int) -> list[User]:
    member_ids = await crud.get_chat_member_user_ids(session, chat_id)
    return await crud.get_users_by_ids(session, member_ids)


async def build_daily_league_report(
    session: AsyncSession, chat_id: int, timezone_name: str
) -> str | None:
    tz = ZoneInfo(timezone_name)
    users = await _users_for_chat(session, chat_id)
    if not users:
        return "Сегодня нет данных для сводки."

    today_local = datetime.now(tz=tz).date()
    yesterday_local = today_local - timedelta(days=1)
    today_start_utc, today_end_utc = _day_bounds_utc(today_local, tz)
    _, yday_end_utc = _day_bounds_utc(yesterday_local, tz)
    sections: dict[str, list[str]] = defaultdict(list)

    for user in users:
        summary = await crud.get_meal_summary_for_period(
            session, user.telegram_id, today_start_utc, today_end_utc
        )
        calories_pct = _pct(summary["calories"], user.daily_calories_target)
        weight_today = await crud.get_latest_weight_at_or_before(
            session, user.telegram_id, today_end_utc
        )
        weight_yesterday = await crud.get_latest_weight_at_or_before(
            session, user.telegram_id, yday_end_utc
        )
        delta_text = _weight_delta_pct(
            weight_today.weight_kg if weight_today else None,
            weight_yesterday.weight_kg if weight_yesterday else None,
        )
        sections[user.goal].append(
            f"- {_user_display_name(user)}: {calories_pct:.1f}% калорий, вес {delta_text}"
        )

    lines = [f"Дневная сводка за {today_local.isoformat()}"]
    for goal in GOAL_ORDER:
        members = sections.get(goal, [])
        if not members:
            continue
        lines.append("")
        lines.append(f"Лига: {GOAL_LABELS.get(goal, goal)}")
        lines.extend(members)

    if len(lines) == 1:
        return "Сегодня нет данных для сводки."
    return "\n".join(lines)


async def build_weekly_league_report(
    session: AsyncSession, chat_id: int, timezone_name: str
) -> str | None:
    tz = ZoneInfo(timezone_name)
    users = await _users_for_chat(session, chat_id)
    if not users:
        return "За неделю нет данных для сводки."

    now_local = datetime.now(tz=tz).date()
    week_start_local = now_local - timedelta(days=now_local.weekday())
    week_start_utc, _ = _day_bounds_utc(week_start_local, tz)
    _, week_end_utc = _day_bounds_utc(now_local, tz)
    sections: dict[str, list[str]] = defaultdict(list)

    for user in users:
        summary = await crud.get_meal_summary_for_period(
            session, user.telegram_id, week_start_utc, week_end_utc
        )
        weekly_target = user.daily_calories_target * 7
        calories_pct = _pct(summary["calories"], weekly_target)
        week_start_weight = await crud.get_latest_weight_at_or_before(
            session, user.telegram_id, week_start_utc
        )
        week_end_weight = await crud.get_latest_weight_at_or_before(
            session, user.telegram_id, week_end_utc
        )
        delta_text = _weight_delta_pct(
            week_end_weight.weight_kg if week_end_weight else None,
            week_start_weight.weight_kg if week_start_weight else None,
        )
        sections[user.goal].append(
            f"- {_user_display_name(user)}: {calories_pct:.1f}% недельной цели, вес {delta_text}"
        )

    lines = [f"Недельная сводка за {week_start_local.isoformat()} - {now_local.isoformat()}"]
    for goal in GOAL_ORDER:
        members = sections.get(goal, [])
        if not members:
            continue
        lines.append("")
        lines.append(f"Лига: {GOAL_LABELS.get(goal, goal)}")
        lines.extend(members)

    if len(lines) == 1:
        return "За неделю нет данных для сводки."
    return "\n".join(lines)
