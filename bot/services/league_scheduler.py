from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from sqlalchemy.ext.asyncio import async_sessionmaker

from bot.database import crud
from bot.services.league_reports import build_daily_league_report, build_weekly_league_report

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
        self._tasks.append(asyncio.create_task(self._run_weight_reminders(), name="weight_reminder_9am"))

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

    def _seconds_until_next_hour(self) -> float:
        now = datetime.now(tz=self._tz)
        target = (now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1))
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
        await _send_weight_reminder_for_user(bot, user_id)


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
    scheduler.start()
    return scheduler
