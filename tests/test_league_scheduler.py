from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from bot.services import league_scheduler


def _sessionmaker_with_session(session_obj: object):
    class _SessionMaker:
        def __call__(self):  # noqa: ANN204
            return self

        async def __aenter__(self):  # noqa: ANN204
            return session_obj

        async def __aexit__(self, exc_type, exc, tb) -> bool:  # noqa: ANN001, ANN204
            _ = (exc_type, exc, tb)
            return False

    return _SessionMaker()


async def test_send_daily_reports_iterates_all_group_chats(monkeypatch) -> None:
    session = object()
    sessionmaker = _sessionmaker_with_session(session)
    bot = MagicMock()
    chat_rows = [SimpleNamespace(chat_id=-10), SimpleNamespace(chat_id=-20)]

    monkeypatch.setattr(league_scheduler.crud, "get_group_chats", AsyncMock(return_value=chat_rows))
    send_daily_for_chat = AsyncMock()
    monkeypatch.setattr(league_scheduler, "_send_daily_for_chat", send_daily_for_chat)

    await league_scheduler.send_daily_reports(bot, sessionmaker, "UTC")

    assert send_daily_for_chat.await_count == 2
    send_daily_for_chat.assert_any_await(bot, sessionmaker, -10, "UTC")
    send_daily_for_chat.assert_any_await(bot, sessionmaker, -20, "UTC")


async def test_send_weekly_reports_iterates_all_group_chats(monkeypatch) -> None:
    session = object()
    sessionmaker = _sessionmaker_with_session(session)
    bot = MagicMock()
    chat_rows = [SimpleNamespace(chat_id=-30)]

    monkeypatch.setattr(league_scheduler.crud, "get_group_chats", AsyncMock(return_value=chat_rows))
    send_weekly_for_chat = AsyncMock()
    monkeypatch.setattr(league_scheduler, "_send_weekly_for_chat", send_weekly_for_chat)

    await league_scheduler.send_weekly_reports(bot, sessionmaker, "UTC")

    send_weekly_for_chat.assert_awaited_once_with(bot, sessionmaker, -30, "UTC")


async def test_start_league_scheduler_fallback_when_apscheduler_missing(monkeypatch) -> None:
    bot = MagicMock()
    sessionmaker = MagicMock()
    monkeypatch.setattr(league_scheduler, "AsyncIOScheduler", None)
    monkeypatch.setattr(league_scheduler, "CronTrigger", None)

    start_mock = MagicMock()
    scheduler_mock = MagicMock(start=start_mock)
    ctor_mock = MagicMock(return_value=scheduler_mock)
    monkeypatch.setattr(league_scheduler, "AsyncioLeagueScheduler", ctor_mock)

    result = league_scheduler.start_league_scheduler(bot, sessionmaker, "UTC")

    ctor_mock.assert_called_once_with(bot=bot, sessionmaker=sessionmaker, timezone_name="UTC")
    start_mock.assert_called_once()
    assert result is scheduler_mock


def test_asyncio_scheduler_seconds_until_positive() -> None:
    scheduler = league_scheduler.AsyncioLeagueScheduler(
        bot=MagicMock(),
        sessionmaker=MagicMock(),
        timezone_name="UTC",
    )
    seconds = scheduler._seconds_until(hour=23, minute=0)
    assert seconds >= 1.0
