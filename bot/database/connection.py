from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

logger = logging.getLogger(__name__)

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def init_engine(database_url: str) -> None:
    global _engine, _sessionmaker
    _engine = create_async_engine(database_url, echo=False, future=True)
    _sessionmaker = async_sessionmaker(bind=_engine, expire_on_commit=False)


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    if _sessionmaker is None:
        raise RuntimeError("Database engine is not initialized. Call init_engine first.")
    return _sessionmaker


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        yield session


def _run_alembic_upgrade(database_url: str) -> None:
    """Apply all pending Alembic migrations (sync, safe to call from a thread)."""
    project_root = Path(__file__).resolve().parents[2]
    alembic_cfg = Config(str(project_root / "alembic.ini"))
    alembic_cfg.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(alembic_cfg, "head")


async def init_db() -> None:
    if _engine is None:
        raise RuntimeError("Database engine is not initialized. Call init_engine first.")
    url = str(_engine.url)
    await asyncio.to_thread(_run_alembic_upgrade, url)
    logger.info("Database migrations applied successfully")
