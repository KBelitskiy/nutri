from __future__ import annotations

import time
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import Message


class OpenAIRateLimitMiddleware(BaseMiddleware):
    def __init__(self, max_requests_per_minute: int = 20) -> None:
        super().__init__()
        self.max_requests = max_requests_per_minute
        self.user_calls: dict[int, deque[float]] = defaultdict(deque)

    async def __call__(
        self,
        handler: Callable[[Message, dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: dict[str, Any],
    ) -> Any:
        if not isinstance(event, Message) or not event.from_user:
            return await handler(event, data)

        user_id = event.from_user.id
        now = time.time()
        calls = self.user_calls[user_id]
        one_minute_ago = now - 60
        while calls and calls[0] < one_minute_ago:
            calls.popleft()

        if len(calls) >= self.max_requests:
            await event.answer("Слишком много запросов к ИИ. Попробуйте через минуту.")
            return None

        calls.append(now)
        return await handler(event, data)

