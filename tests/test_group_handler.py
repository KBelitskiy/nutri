from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from bot.handlers import group as group_handler


def _make_ctx(session_obj: object, timezone_name: str = "UTC") -> SimpleNamespace:
    class _SessionMaker:
        def __call__(self):  # noqa: ANN204
            return self

        async def __aenter__(self):  # noqa: ANN204
            return session_obj

        async def __aexit__(self, exc_type, exc, tb) -> bool:  # noqa: ANN001, ANN204
            _ = (exc_type, exc, tb)
            return False

    return SimpleNamespace(
        sessionmaker=_SessionMaker(),
        settings=SimpleNamespace(league_report_timezone=timezone_name),
    )


async def test_group_start_replies_with_hint(monkeypatch) -> None:
    message = MagicMock()
    message.answer = AsyncMock()
    await group_handler.group_start(message)
    message.answer.assert_awaited_once()
    text = message.answer.await_args.args[0]
    assert "/league_today" in text
    assert "/league_week" in text
    assert message.answer.await_args.kwargs["reply_markup"] == group_handler.GROUP_MENU_KB


async def test_manual_daily_report_calls_services(monkeypatch) -> None:
    session = object()
    ctx = _make_ctx(session)
    monkeypatch.setattr(group_handler, "get_app_context", lambda: ctx)
    add_group = AsyncMock()
    ensure_member = AsyncMock()
    build_daily = AsyncMock(return_value="daily-report")
    monkeypatch.setattr(group_handler.crud, "add_group_chat", add_group)
    monkeypatch.setattr(group_handler.crud, "ensure_group_member", ensure_member)
    monkeypatch.setattr(group_handler, "build_daily_league_report", build_daily)

    message = MagicMock()
    message.from_user = SimpleNamespace(id=123)
    message.chat = SimpleNamespace(id=-1001, title="Chat")
    message.answer = AsyncMock()

    await group_handler.send_manual_daily_league_report(message)

    add_group.assert_awaited_once_with(session, -1001, title="Chat")
    ensure_member.assert_awaited_once_with(session, -1001, 123)
    build_daily.assert_awaited_once_with(session, -1001, "UTC")
    message.answer.assert_awaited_once_with("daily-report")


async def test_manual_weekly_report_uses_fallback_text(monkeypatch) -> None:
    session = object()
    ctx = _make_ctx(session)
    monkeypatch.setattr(group_handler, "get_app_context", lambda: ctx)
    monkeypatch.setattr(group_handler.crud, "add_group_chat", AsyncMock())
    monkeypatch.setattr(group_handler.crud, "ensure_group_member", AsyncMock())
    monkeypatch.setattr(group_handler, "build_weekly_league_report", AsyncMock(return_value=None))

    message = MagicMock()
    message.from_user = SimpleNamespace(id=234)
    message.chat = SimpleNamespace(id=-1002, title="Chat")
    message.answer = AsyncMock()

    await group_handler.send_manual_weekly_league_report(message)

    message.answer.assert_awaited_once_with("За неделю нет данных для сводки.")


async def test_register_group_message_author_skips_without_user(monkeypatch) -> None:
    session = object()
    ctx = _make_ctx(session)
    monkeypatch.setattr(group_handler, "get_app_context", lambda: ctx)
    add_group = AsyncMock()
    ensure_member = AsyncMock()
    monkeypatch.setattr(group_handler.crud, "add_group_chat", add_group)
    monkeypatch.setattr(group_handler.crud, "ensure_group_member", ensure_member)

    message = MagicMock()
    message.from_user = None
    message.chat = SimpleNamespace(id=-1003, title="Chat")

    await group_handler.register_group_message_author(message)

    add_group.assert_not_called()
    ensure_member.assert_not_called()


async def test_bot_chat_member_update_adds_group_chat(monkeypatch) -> None:
    session = object()
    ctx = _make_ctx(session)
    monkeypatch.setattr(group_handler, "get_app_context", lambda: ctx)
    add_group = AsyncMock()
    remove_group = AsyncMock()
    monkeypatch.setattr(group_handler.crud, "add_group_chat", add_group)
    monkeypatch.setattr(group_handler.crud, "remove_group_chat", remove_group)

    event = MagicMock()
    event.chat = SimpleNamespace(type="group", id=-1004, title="Team")
    event.old_chat_member = SimpleNamespace(status="left")
    event.new_chat_member = SimpleNamespace(status="member")

    await group_handler.bot_chat_member_update(event)

    add_group.assert_awaited_once_with(session, -1004, title="Team")
    remove_group.assert_not_called()


async def test_bot_chat_member_update_removes_group_chat(monkeypatch) -> None:
    session = object()
    ctx = _make_ctx(session)
    monkeypatch.setattr(group_handler, "get_app_context", lambda: ctx)
    add_group = AsyncMock()
    remove_group = AsyncMock()
    monkeypatch.setattr(group_handler.crud, "add_group_chat", add_group)
    monkeypatch.setattr(group_handler.crud, "remove_group_chat", remove_group)

    event = MagicMock()
    event.chat = SimpleNamespace(type="supergroup", id=-1005, title="Team")
    event.old_chat_member = SimpleNamespace(status="member")
    event.new_chat_member = SimpleNamespace(status="left")

    await group_handler.bot_chat_member_update(event)

    remove_group.assert_awaited_once_with(session, -1005)
    add_group.assert_not_called()
