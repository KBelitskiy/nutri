from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import async_sessionmaker

from bot.config import Settings
from bot.services.ai_agent import AIAgent


@dataclass(slots=True)
class AppContext:
    settings: Settings
    sessionmaker: async_sessionmaker
    agent: AIAgent


app_context: AppContext | None = None


def set_app_context(ctx: AppContext) -> None:
    global app_context
    app_context = ctx


def get_app_context() -> AppContext:
    if app_context is None:
        raise RuntimeError("App context is not initialized")
    return app_context

