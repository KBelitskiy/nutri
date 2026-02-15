"""Тесты middleware лимита запросов к OpenAI (bot.middlewares.rate_limit)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.middlewares.rate_limit import OpenAIRateLimitMiddleware


@pytest.fixture
def middleware() -> OpenAIRateLimitMiddleware:
    return OpenAIRateLimitMiddleware(max_requests_per_minute=2)


@pytest.fixture
def message() -> MagicMock:
    m = MagicMock()
    # один и тот же объект user, чтобы user_calls[user.id] был один и тот же deque
    user = MagicMock()
    user.id = 12345
    m.from_user = user
    m.answer = AsyncMock()
    return m


@pytest.fixture
def handler() -> AsyncMock:
    return AsyncMock(return_value="handled")


async def test_allows_requests_under_limit(
    middleware: OpenAIRateLimitMiddleware, message: MagicMock, handler: AsyncMock
) -> None:
    result = await middleware(handler, message, {})
    assert result == "handled"
    assert handler.await_count == 1


async def test_blocks_when_over_limit(handler: AsyncMock) -> None:
    # при превышении лимита middleware возвращает None и не вызывает handler
    from collections import deque
    from datetime import datetime

    from aiogram.types import Chat, Message, User

    t = 1000000.0
    answer_mock = AsyncMock()
    with patch("bot.middlewares.rate_limit.time.time", return_value=t):
        with patch.object(Message, "answer", answer_mock):
            user = User(id=999, is_bot=False, first_name="T")
            chat = Chat(id=1, type="private")
            msg = Message(
                message_id=1,
                date=datetime.now(),
                chat=chat,
                from_user=user,
            )
            middleware = OpenAIRateLimitMiddleware(max_requests_per_minute=2)
            middleware.user_calls[999] = deque([t, t])
            result = await middleware(handler, msg, {})
    assert result is None
    assert handler.await_count == 0
    answer_mock.assert_called_once()
    assert "минуту" in answer_mock.call_args[0][0].lower() or "много" in answer_mock.call_args[0][0].lower()


async def test_non_message_passes_through(
    middleware: OpenAIRateLimitMiddleware, handler: AsyncMock
) -> None:
    not_message = MagicMock()
    not_message.from_user = None
    result = await middleware(handler, not_message, {})
    assert result == "handled"


async def test_message_without_from_user_passes_through(
    middleware: OpenAIRateLimitMiddleware, handler: AsyncMock
) -> None:
    msg = MagicMock()
    msg.from_user = None
    result = await middleware(handler, msg, {})
    assert result == "handled"
