"""Фикстуры для тестов: in-memory SQLite, сессии, sessionmaker."""
from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from bot.database.models import Base


@pytest.fixture
async def db_engine():
    """Движок БД в памяти для тестов."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def sessionmaker(db_engine):
    """Sessionmaker, привязанный к тестовому движку."""
    return async_sessionmaker(
        bind=db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )


@pytest.fixture
async def session(sessionmaker) -> AsyncGenerator[AsyncSession, None]:
    """Одна сессия на тест; после теста откат не нужен — БД в памяти новая на каждый db_engine."""
    async with sessionmaker() as s:
        yield s
