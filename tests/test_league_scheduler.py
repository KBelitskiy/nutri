from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

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


async def test_send_weight_reminders_sends_only_to_matching_timezones(monkeypatch) -> None:
    session = object()
    sessionmaker = _sessionmaker_with_session(session)
    bot = MagicMock()

    monkeypatch.setattr(
        league_scheduler.crud,
        "get_distinct_user_timezones",
        AsyncMock(return_value=["Europe/Moscow", "America/New_York", None]),
    )
    monkeypatch.setattr(
        league_scheduler.crud,
        "get_user_ids_by_timezones",
        AsyncMock(return_value=[101, 202]),
    )
    monkeypatch.setattr(
        league_scheduler,
        "_timezones_with_hour",
        lambda tzs, target_hour, fallback_tz: ["Europe/Moscow"],
    )
    send_for_user = AsyncMock()
    monkeypatch.setattr(league_scheduler, "_send_weight_reminder_for_user", send_for_user)

    await league_scheduler.send_weight_reminders(bot, sessionmaker, "UTC")

    assert send_for_user.await_count == 2
    send_for_user.assert_any_await(bot, 101)
    send_for_user.assert_any_await(bot, 202)


async def test_send_weight_reminders_skips_when_no_matching_tz(monkeypatch) -> None:
    session = object()
    sessionmaker = _sessionmaker_with_session(session)
    bot = MagicMock()

    monkeypatch.setattr(
        league_scheduler.crud,
        "get_distinct_user_timezones",
        AsyncMock(return_value=["Europe/Moscow"]),
    )
    monkeypatch.setattr(
        league_scheduler,
        "_timezones_with_hour",
        lambda tzs, target_hour, fallback_tz: [],
    )
    send_for_user = AsyncMock()
    monkeypatch.setattr(league_scheduler, "_send_weight_reminder_for_user", send_for_user)

    await league_scheduler.send_weight_reminders(bot, sessionmaker, "UTC")

    send_for_user.assert_not_awaited()


def test_start_league_scheduler_adds_weight_reminder_job(monkeypatch) -> None:
    class _DummyScheduler:
        def __init__(self, timezone):  # noqa: ANN001
            self.timezone = timezone
            self.jobs = []
            self.started = False

        def add_job(self, func, trigger, kwargs, id, replace_existing):  # noqa: ANN001, A002
            self.jobs.append(
                {
                    "func": func,
                    "trigger": trigger,
                    "kwargs": kwargs,
                    "id": id,
                    "replace_existing": replace_existing,
                }
            )

        def start(self):  # noqa: D401
            self.started = True

    class _DummyCron:
        def __init__(self, **kw):  # noqa: ANN003
            self.kw = kw

    bot = MagicMock()
    sessionmaker = MagicMock()
    monkeypatch.setattr(league_scheduler, "AsyncIOScheduler", _DummyScheduler)
    monkeypatch.setattr(league_scheduler, "CronTrigger", _DummyCron)

    scheduler = league_scheduler.start_league_scheduler(bot, sessionmaker, "UTC")

    assert scheduler.started is True
    ids = {j["id"] for j in scheduler.jobs}
    assert "weight_reminder_hourly" in ids
    weight_job = next(j for j in scheduler.jobs if j["id"] == "weight_reminder_hourly")
    assert weight_job["func"] is league_scheduler.send_weight_reminders
    assert weight_job["trigger"].kw["minute"] == 0
    assert "hour" not in weight_job["trigger"].kw


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


def test_timezones_with_hour_filters_correctly() -> None:
    fixed_utc = datetime(2025, 6, 15, 6, 0, 0, tzinfo=ZoneInfo("UTC"))
    with patch("bot.services.league_scheduler.datetime") as mock_dt:
        mock_dt.now = lambda tz: fixed_utc.astimezone(tz)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        result = league_scheduler._timezones_with_hour(
            ["Europe/Moscow", "America/New_York", "UTC", None],
            target_hour=9,
            fallback_tz="Europe/London",
        )
    assert "Europe/Moscow" in result
    assert "America/New_York" not in result
    assert "UTC" not in result


def test_timezones_with_hour_uses_fallback_for_none() -> None:
    fixed_utc = datetime(2025, 6, 15, 6, 0, 0, tzinfo=ZoneInfo("UTC"))
    with patch("bot.services.league_scheduler.datetime") as mock_dt:
        mock_dt.now = lambda tz: fixed_utc.astimezone(tz)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        result = league_scheduler._timezones_with_hour(
            [None],
            target_hour=9,
            fallback_tz="Europe/Moscow",
        )
    assert None in result


def test_asyncio_scheduler_seconds_until_positive() -> None:
    scheduler = league_scheduler.AsyncioLeagueScheduler(
        bot=MagicMock(),
        sessionmaker=MagicMock(),
        timezone_name="UTC",
    )
    seconds = scheduler._seconds_until(hour=23, minute=0)
    assert seconds >= 1.0
