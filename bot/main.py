from __future__ import annotations

import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from bot.config import load_settings
from bot.database.connection import get_sessionmaker, init_db, init_engine
from bot.handlers import ALL_ROUTERS
from bot.middlewares.rate_limit import OpenAIRateLimitMiddleware
from bot.runtime import AppContext, set_app_context
from bot.services.ai_agent import AIAgent
from bot.services.league_scheduler import start_league_scheduler
from bot.tools.meal_tools import meal_tool_handlers, meal_tools_schema
from bot.tools.stats_tools import stats_tool_handlers, stats_tools_schema
from bot.tools.user_tools import user_tool_handlers, user_tools_schema
from bot.tools.weight_tools import weight_tool_handlers, weight_tools_schema


def configure_agent(ctx: AppContext) -> None:
    schemas = []
    handlers = {}
    schemas.extend(meal_tools_schema())
    schemas.extend(stats_tools_schema())
    schemas.extend(user_tools_schema())
    schemas.extend(weight_tools_schema())
    handlers.update(meal_tool_handlers(ctx.sessionmaker, timezone_name=ctx.settings.league_report_timezone))
    handlers.update(stats_tool_handlers(ctx.sessionmaker))
    handlers.update(user_tool_handlers(ctx.sessionmaker))
    handlers.update(weight_tool_handlers(ctx.sessionmaker))
    ctx.agent.register_tools(schemas, handlers)


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    settings = load_settings()
    if settings.openai_base_url:
        # Дублируем в env, чтобы SDK и любые внутренние клиенты использовали тот же endpoint.
        os.environ["OPENAI_BASE_URL"] = settings.openai_base_url
    logging.info("OpenAI base URL: %s", settings.openai_base_url or "default")
    init_engine(settings.database_url)
    await init_db()

    bot = Bot(token=settings.telegram_bot_token)
    dp = Dispatcher(storage=MemoryStorage())
    dp.message.middleware(OpenAIRateLimitMiddleware(settings.openai_max_requests_per_minute))

    agent = AIAgent(
        api_key=settings.openai_api_key,
        model=settings.openai_model_text,
        base_url=settings.openai_base_url,
        vision_model=settings.openai_model_vision,
    )
    ctx = AppContext(settings=settings, sessionmaker=get_sessionmaker(), agent=agent)
    set_app_context(ctx)
    configure_agent(ctx)

    for router in ALL_ROUTERS:
        dp.include_router(router)
    scheduler = start_league_scheduler(
        bot=bot,
        sessionmaker=ctx.sessionmaker,
        timezone_name=ctx.settings.league_report_timezone,
    )
    try:
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown(wait=False)


if __name__ == "__main__":
    asyncio.run(main())

