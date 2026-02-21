from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from sqlalchemy.ext.asyncio import async_sessionmaker

from bot.database import crud
from bot.prompts.loader import load as load_prompt
from bot.runtime import get_app_context
from bot.services.league_reports import build_daily_league_report, build_weekly_league_report
from bot.services.streaks import evaluate_daily_streak_for_user
from bot.services.weight_plan import calculate_plan_targets, compare_progress, get_expected_weight_for_date

logger = logging.getLogger(__name__)

try:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.cron import CronTrigger
except ImportError:  # pragma: no cover - ветка зависит от окружения
    AsyncIOScheduler = None  # type: ignore[assignment]
    CronTrigger = None  # type: ignore[assignment]


class AsyncioLeagueScheduler:
    def __init__(self, bot: Bot, sessionmaker: async_sessionmaker, timezone_name: str) -> None:
        self.bot = bot
        self.sessionmaker = sessionmaker
        self.timezone_name = timezone_name
        self._tz = ZoneInfo(timezone_name)
        self._tasks: list[asyncio.Task] = []

    def start(self) -> None:
        self._tasks.append(asyncio.create_task(self._run_daily(), name="league_daily_report"))
        self._tasks.append(asyncio.create_task(self._run_weekly(), name="league_weekly_report"))
        self._tasks.append(asyncio.create_task(self._run_weekly_coaching(), name="weekly_coaching_hourly"))
        self._tasks.append(asyncio.create_task(self._run_weight_reminders(), name="weight_reminder_9am"))
        self._tasks.append(asyncio.create_task(self._run_meal_reminders(), name="meal_reminder_hourly"))
        self._tasks.append(asyncio.create_task(self._run_weight_plan_checks(), name="weight_plan_check_10am"))
        self._tasks.append(asyncio.create_task(self._run_streak_checks(), name="daily_streak_check_2330"))

    def shutdown(self, wait: bool = False) -> None:
        _ = wait
        for task in self._tasks:
            task.cancel()
        self._tasks.clear()

    async def _run_daily(self) -> None:
        while True:
            await asyncio.sleep(self._seconds_until(hour=23, minute=0))
            await send_daily_reports(self.bot, self.sessionmaker, self.timezone_name)

    async def _run_weekly(self) -> None:
        while True:
            await asyncio.sleep(self._seconds_until(hour=23, minute=0, weekday=6))
            await send_weekly_reports(self.bot, self.sessionmaker, self.timezone_name)

    async def _run_weight_reminders(self) -> None:
        while True:
            await asyncio.sleep(self._seconds_until_next_hour())
            await send_weight_reminders(self.bot, self.sessionmaker, self.timezone_name)

    async def _run_weekly_coaching(self) -> None:
        while True:
            await asyncio.sleep(self._seconds_until_next_hour())
            await send_weekly_coaching(self.bot, self.sessionmaker, self.timezone_name)

    async def _run_weight_plan_checks(self) -> None:
        while True:
            await asyncio.sleep(self._seconds_until_next_hour())
            await send_weight_plan_checks(self.bot, self.sessionmaker, self.timezone_name)

    async def _run_meal_reminders(self) -> None:
        while True:
            await asyncio.sleep(self._seconds_until_next_hour())
            await send_meal_reminders(self.bot, self.sessionmaker, self.timezone_name)

    async def _run_streak_checks(self) -> None:
        while True:
            await asyncio.sleep(self._seconds_until_next_half_hour())
            await send_daily_streak_checks(self.bot, self.sessionmaker, self.timezone_name)

    def _seconds_until_next_hour(self) -> float:
        now = datetime.now(tz=self._tz)
        target = (now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1))
        return max(1.0, (target - now).total_seconds())

    def _seconds_until_next_half_hour(self) -> float:
        now = datetime.now(tz=self._tz)
        if now.minute < 30:
            target = now.replace(minute=30, second=0, microsecond=0)
        else:
            target = (now.replace(minute=30, second=0, microsecond=0) + timedelta(hours=1))
        return max(1.0, (target - now).total_seconds())

    def _seconds_until(self, hour: int, minute: int, weekday: int | None = None) -> float:
        now = datetime.now(tz=self._tz)
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if weekday is None:
            if now >= target:
                target += timedelta(days=1)
        else:
            days_ahead = (weekday - now.weekday()) % 7
            if days_ahead == 0 and now >= target:
                days_ahead = 7
            target += timedelta(days=days_ahead)
        return max(1.0, (target - now).total_seconds())


async def _group_chat_ids(sessionmaker: async_sessionmaker) -> list[int]:
    async with sessionmaker() as session:
        chats = await crud.get_group_chats(session)
    return [chat.chat_id for chat in chats]


async def _user_ids(sessionmaker: async_sessionmaker) -> list[int]:
    async with sessionmaker() as session:
        return await crud.get_all_user_ids(session)


def _timezones_with_hour(timezones: list[str | None], target_hour: int, fallback_tz: str) -> list[str | None]:
    """Return timezone names from *timezones* where the local hour equals *target_hour* right now."""
    matching: list[str | None] = []
    for tz_name in timezones:
        effective = tz_name or fallback_tz
        try:
            now_local = datetime.now(tz=ZoneInfo(effective))
        except (KeyError, Exception):  # noqa: BLE001
            continue
        if now_local.hour == target_hour:
            matching.append(tz_name)
    return matching


async def _send_weight_reminder_for_user(bot: Bot, user_id: int) -> None:
    text = "Доброе утро! Не забудь взвеситься и отправить вес командой /weight."
    try:
        await bot.send_message(chat_id=user_id, text=text)
    except (TelegramForbiddenError, TelegramBadRequest):
        logger.warning("Cannot send weight reminder to user %s (chat unavailable)", user_id)
    except Exception:  # noqa: BLE001
        logger.exception("Failed to send weight reminder to user %s", user_id)


async def _send_user_text(bot: Bot, user_id: int, text: str) -> None:
    try:
        await bot.send_message(chat_id=user_id, text=text)
    except (TelegramForbiddenError, TelegramBadRequest):
        logger.warning("Cannot send message to user %s (chat unavailable)", user_id)
    except Exception:  # noqa: BLE001
        logger.exception("Failed to send message to user %s", user_id)


async def _send_daily_for_chat(
    bot: Bot, sessionmaker: async_sessionmaker, chat_id: int, timezone_name: str
) -> None:
    async with sessionmaker() as session:
        report = await build_daily_league_report(session, chat_id, timezone_name)
    if not report:
        return
    try:
        await bot.send_message(chat_id=chat_id, text=report)
    except (TelegramForbiddenError, TelegramBadRequest):
        logger.warning("Removing unavailable chat %s after daily report failure", chat_id)
        async with sessionmaker() as session:
            await crud.remove_group_chat(session, chat_id)
    except Exception:  # noqa: BLE001
        logger.exception("Failed to send daily report to chat %s", chat_id)


async def _send_weekly_for_chat(
    bot: Bot, sessionmaker: async_sessionmaker, chat_id: int, timezone_name: str
) -> None:
    async with sessionmaker() as session:
        report = await build_weekly_league_report(session, chat_id, timezone_name)
    if not report:
        return
    try:
        await bot.send_message(chat_id=chat_id, text=report)
    except (TelegramForbiddenError, TelegramBadRequest):
        logger.warning("Removing unavailable chat %s after weekly report failure", chat_id)
        async with sessionmaker() as session:
            await crud.remove_group_chat(session, chat_id)
    except Exception:  # noqa: BLE001
        logger.exception("Failed to send weekly report to chat %s", chat_id)


async def send_daily_reports(bot: Bot, sessionmaker: async_sessionmaker, timezone_name: str) -> None:
    for chat_id in await _group_chat_ids(sessionmaker):
        await _send_daily_for_chat(bot, sessionmaker, chat_id, timezone_name)


async def send_weekly_reports(bot: Bot, sessionmaker: async_sessionmaker, timezone_name: str) -> None:
    for chat_id in await _group_chat_ids(sessionmaker):
        await _send_weekly_for_chat(bot, sessionmaker, chat_id, timezone_name)


async def send_weight_reminders(bot: Bot, sessionmaker: async_sessionmaker, timezone_name: str) -> None:
    """Send weight reminders only to users whose local time is currently 9 AM."""
    async with sessionmaker() as session:
        all_tz = await crud.get_distinct_user_timezones(session)
    matching = _timezones_with_hour(all_tz, target_hour=9, fallback_tz=timezone_name)
    if not matching:
        return
    async with sessionmaker() as session:
        user_ids = await crud.get_user_ids_by_timezones(session, matching)
    for user_id in user_ids:
        has_weight_today = False
        try:
            async with sessionmaker() as session:
                has_weight_today = await crud.has_weight_log_today(
                    session,
                    user_id,
                    timezone=ZoneInfo(timezone_name),
                )
        except Exception:  # noqa: BLE001
            logger.debug("Skip has_weight_log_today check for user %s", user_id)
        if has_weight_today:
            continue
        await _send_weight_reminder_for_user(bot, user_id)


async def send_weight_plan_checks(bot: Bot, sessionmaker: async_sessionmaker, timezone_name: str) -> None:
    # Получаем только ID, чтобы объекты User не стали detached после закрытия сессии.
    async with sessionmaker() as session:
        plan_users = await crud.get_users_with_active_plan(session)
        user_ids = [u.telegram_id for u in plan_users]

    for user_id in user_ids:
        # Одна сессия на весь цикл обработки пользователя: читаем и пишем в ней же,
        # поэтому user отслеживается session и изменения корректно сохраняются.
        async with sessionmaker() as session:
            user = await crud.get_user(session, user_id)
            if user is None:
                continue

            tz_name = user.timezone or timezone_name
            try:
                user_tz = ZoneInfo(tz_name)
            except Exception:  # noqa: BLE001
                user_tz = ZoneInfo(timezone_name)
            now_local = datetime.now(tz=user_tz)
            if now_local.hour != 10:
                continue

            latest = await crud.get_latest_weight(session, user.telegram_id)
            if latest is None:
                continue

            latest_local_date = latest.logged_at.astimezone(user_tz).date() if latest.logged_at else None
            if latest_local_date != now_local.date():
                continue

            if (
                user.weight_plan_mode is None
                or user.target_weight_kg is None
                or user.weight_plan_start_date is None
                or user.weight_plan_start_kg is None
            ):
                continue

            expected = get_expected_weight_for_date(
                plan_start_date=user.weight_plan_start_date,
                plan_start_kg=float(user.weight_plan_start_kg),
                target_weight=float(user.target_weight_kg),
                mode=user.weight_plan_mode,
                gender=user.gender,
                age=user.age,
                height_cm=user.height_cm,
                activity_level=user.activity_level,
                check_date=datetime.now(tz=UTC),
            )
            actual = float(latest.weight_kg)
            progress = compare_progress(
                expected_kg=expected,
                actual_kg=actual,
                target_weight=float(user.target_weight_kg),
                current_weight=float(user.weight_plan_start_kg),
            )

            if user.goal == "lose" and actual <= float(user.target_weight_kg):
                await _send_user_text(
                    bot,
                    user.telegram_id,
                    (
                        "Отличная работа! Цель по весу достигнута 🎉\n"
                        "Рекомендую перейти на режим поддержания и закрепить результат."
                    ),
                )
                continue
            if user.goal == "gain" and actual >= float(user.target_weight_kg):
                await _send_user_text(
                    bot,
                    user.telegram_id,
                    (
                        "Поздравляю, цель по набору достигнута 🎉\n"
                        "Дальше можно перейти на поддержание, чтобы стабилизировать вес."
                    ),
                )
                continue

            lagging = not bool(progress["on_track"]) and float(progress["deviation_kg"]) > 0.5
            if lagging:
                mode_order = ["light", "medium", "hard"]
                current_mode = user.weight_plan_mode if user.weight_plan_mode in mode_order else "medium"
                current_idx = mode_order.index(current_mode)
                next_mode = mode_order[min(current_idx + 1, len(mode_order) - 1)]

                targets = calculate_plan_targets(
                    current_weight=actual,
                    target_weight=float(user.target_weight_kg),
                    gender=user.gender,
                    age=user.age,
                    height_cm=user.height_cm,
                    activity_level=user.activity_level,
                    mode=next_mode,
                )
                user.weight_plan_mode = next_mode
                user.daily_calories_target = float(targets["daily_calories"])
                user.daily_protein_target = float(targets["daily_protein"])
                user.daily_fat_target = float(targets["daily_fat"])
                user.daily_carbs_target = float(targets["daily_carbs"])
                await session.commit()

                await _send_user_text(
                    bot,
                    user.telegram_id,
                    (
                        f"Есть отставание от плана: {progress['deviation_kg']:+.2f} кг.\n"
                        f"Ожидалось: {expected:.2f} кг, факт: {actual:.2f} кг.\n"
                        f"Скорректировал режим на {next_mode}: {targets['daily_calories']:.0f} ккал/день.\n"
                        "Усиль контроль порций и ежедневную активность (шаги/кардио)."
                    ),
                )
                continue

            # Поддержка не ежедневно, примерно раз в 4 дня.
            if now_local.toordinal() % 4 == 0:
                await _send_user_text(
                    bot,
                    user.telegram_id,
                    (
                        "Ты идешь по плану. Отличный темп!\n"
                        f"Сегодня: факт {actual:.2f} кг, ожидалось {expected:.2f} кг."
                    ),
                )


def _parse_reminder_hours(value: str | None) -> set[int]:
    if not value:
        return {9, 13, 19}
    result: set[int] = set()
    for part in value.split(","):
        token = part.strip()
        if not token:
            continue
        if token.isdigit():
            hour = int(token)
            if 0 <= hour <= 23:
                result.add(hour)
    return result or {9, 13, 19}


async def send_meal_reminders(bot: Bot, sessionmaker: async_sessionmaker, timezone_name: str) -> None:
    async with sessionmaker() as session:
        user_ids = await crud.get_all_user_ids(session)
    if not user_ids:
        return
    async with sessionmaker() as session:
        users = await crud.get_users_by_ids(session, user_ids)

    for user in users:
        tz_name = user.timezone or timezone_name
        try:
            user_tz = ZoneInfo(tz_name)
        except Exception:  # noqa: BLE001
            user_tz = ZoneInfo(timezone_name)
        now_local = datetime.now(tz=user_tz)
        reminder_hours = _parse_reminder_hours(user.meal_reminder_times)

        if now_local.hour == 21:
            async with sessionmaker() as session:
                consumed = await crud.get_meal_summary_for_day(
                    session,
                    user.telegram_id,
                    timezone=user_tz,
                )
            if consumed.get("calories", 0.0) < float(user.daily_calories_target) * 0.6:
                await _send_user_text(
                    bot,
                    user.telegram_id,
                    (
                        f"Ты записал {consumed.get('calories', 0.0):.0f} из "
                        f"{user.daily_calories_target:.0f} ккал. "
                        "Проверь, не забыл ли записать приемы пищи."
                    ),
                )
            continue

        if now_local.hour not in reminder_hours:
            continue
        async with sessionmaker() as session:
            has_recent = await crud.has_meals_in_last_hours(
                session,
                user.telegram_id,
                hours=2,
                now=datetime.now(tz=UTC),
            )
        if has_recent:
            continue
        await _send_user_text(
            bot,
            user.telegram_id,
            f"Уже {now_local.hour:02d}:00. Не забудь записать прием пищи.",
        )


async def send_weekly_coaching(bot: Bot, sessionmaker: async_sessionmaker, timezone_name: str) -> None:
    async with sessionmaker() as session:
        user_ids = await crud.get_all_user_ids(session)
    if not user_ids:
        return
    async with sessionmaker() as session:
        users = await crud.get_users_by_ids(session, user_ids)
    app_ctx = get_app_context()

    for user in users:
        tz_name = user.timezone or timezone_name
        try:
            user_tz = ZoneInfo(tz_name)
        except Exception:  # noqa: BLE001
            user_tz = ZoneInfo(timezone_name)
        now_local = datetime.now(tz=user_tz)
        if now_local.weekday() != 6 or now_local.hour != 20:
            continue

        async with sessionmaker() as session:
            payload = await crud.get_weekly_coaching_data(
                session,
                user.telegram_id,
                days=7,
                timezone=user_tz,
            )
        if "error" in payload:
            continue
        prompt = load_prompt(
            "coaching/weekly",
            profile=json.dumps(payload["profile"], ensure_ascii=False),
            daily_totals=json.dumps(payload["daily_totals"], ensure_ascii=False),
            weight_history=json.dumps(payload["weight_history"], ensure_ascii=False),
        )
        try:
            answer = await app_ctx.agent.ask(prompt, use_tools=False)
        except Exception:  # noqa: BLE001
            logger.exception("Failed to generate weekly coaching for user %s", user.telegram_id)
            continue
        await _send_user_text(bot, user.telegram_id, answer)


async def send_daily_streak_checks(bot: Bot, sessionmaker: async_sessionmaker, timezone_name: str) -> None:
    """Evaluate daily streaks for users whose local time is 23:30."""
    async with sessionmaker() as session:
        all_tz = await crud.get_distinct_user_timezones(session)
    matching = _timezones_with_hour(all_tz, target_hour=23, fallback_tz=timezone_name)
    if not matching:
        return
    async with sessionmaker() as session:
        user_ids = await crud.get_user_ids_by_timezones(session, matching)

    for user_id in user_ids:
        async with sessionmaker() as session:
            user = await crud.get_user(session, user_id)
            if user is None:
                continue
            tz_name = user.timezone or timezone_name
            try:
                user_tz = ZoneInfo(tz_name)
            except Exception:  # noqa: BLE001
                user_tz = ZoneInfo(timezone_name)
            result = await evaluate_daily_streak_for_user(
                session,
                user_id,
                timezone=user_tz,
            )

        if "error" in result:
            continue
        new_badges = list(result.get("new_badges", []))
        streak_days = int(result.get("streak_days", 0))
        if not new_badges:
            continue
        badges_text = ", ".join(new_badges)
        await _send_user_text(
            bot,
            user_id,
            (
                f"Новый бейдж: {badges_text}.\n"
                f"Текущий стрик по калориям: {streak_days} дн. Продолжай в том же темпе!"
            ),
        )


def start_league_scheduler(
    bot: Bot, sessionmaker: async_sessionmaker, timezone_name: str
) -> AsyncIOScheduler | AsyncioLeagueScheduler:
    tz = ZoneInfo(timezone_name)
    if AsyncIOScheduler is None or CronTrigger is None:
        logger.warning(
            "apscheduler is not installed; using asyncio fallback scheduler for league reports"
        )
        scheduler = AsyncioLeagueScheduler(
            bot=bot,
            sessionmaker=sessionmaker,
            timezone_name=timezone_name,
        )
        scheduler.start()
        return scheduler

    scheduler = AsyncIOScheduler(timezone=tz)
    scheduler.add_job(
        send_daily_reports,
        CronTrigger(hour=23, minute=0, timezone=tz),
        kwargs={"bot": bot, "sessionmaker": sessionmaker, "timezone_name": timezone_name},
        id="league_daily_report",
        replace_existing=True,
    )
    scheduler.add_job(
        send_weekly_reports,
        CronTrigger(day_of_week="sun", hour=23, minute=0, timezone=tz),
        kwargs={"bot": bot, "sessionmaker": sessionmaker, "timezone_name": timezone_name},
        id="league_weekly_report",
        replace_existing=True,
    )
    scheduler.add_job(
        send_weight_reminders,
        CronTrigger(minute=0, timezone=tz),
        kwargs={"bot": bot, "sessionmaker": sessionmaker, "timezone_name": timezone_name},
        id="weight_reminder_hourly",
        replace_existing=True,
    )
    scheduler.add_job(
        send_weekly_coaching,
        CronTrigger(minute=0, timezone=tz),
        kwargs={"bot": bot, "sessionmaker": sessionmaker, "timezone_name": timezone_name},
        id="weekly_coaching_hourly",
        replace_existing=True,
    )
    scheduler.add_job(
        send_weight_plan_checks,
        CronTrigger(minute=0, timezone=tz),
        kwargs={"bot": bot, "sessionmaker": sessionmaker, "timezone_name": timezone_name},
        id="weight_plan_check_hourly",
        replace_existing=True,
    )
    scheduler.add_job(
        send_meal_reminders,
        CronTrigger(minute=0, timezone=tz),
        kwargs={"bot": bot, "sessionmaker": sessionmaker, "timezone_name": timezone_name},
        id="meal_reminder_hourly",
        replace_existing=True,
    )
    scheduler.add_job(
        send_daily_streak_checks,
        CronTrigger(minute=30, timezone=tz),
        kwargs={"bot": bot, "sessionmaker": sessionmaker, "timezone_name": timezone_name},
        id="daily_streak_check_2330",
        replace_existing=True,
    )
    scheduler.start()
    return scheduler
