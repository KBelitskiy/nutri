"""Тесты подключения к БД (bot.database.connection)."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from bot.database.connection import get_sessionmaker, init_db, init_engine


def test_get_sessionmaker_raises_before_init() -> None:
    with patch("bot.database.connection._sessionmaker", None):
        with pytest.raises(RuntimeError, match="not initialized"):
            get_sessionmaker()


async def test_init_engine_and_get_sessionmaker() -> None:
    init_engine("sqlite+aiosqlite:///:memory:")
    try:
        sm = get_sessionmaker()
        assert sm is not None
    finally:
        # сброс глобалов, чтобы не влиять на другие тесты
        import bot.database.connection as conn
        conn._engine = None
        conn._sessionmaker = None


async def test_init_db_creates_tables() -> None:
    init_engine("sqlite+aiosqlite:///:memory:")
    try:
        await init_db()
        sm = get_sessionmaker()
        async with sm() as session:
            from sqlalchemy import text
            result = await session.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='users'"))
            row = result.scalar_one_or_none()
            assert row is not None
    finally:
        import bot.database.connection as conn
        if conn._engine:
            await conn._engine.dispose()
        conn._engine = None
        conn._sessionmaker = None


async def test_init_db_raises_without_engine() -> None:
    import bot.database.connection as conn
    old_engine = conn._engine
    conn._engine = None
    try:
        with pytest.raises(RuntimeError, match="not initialized"):
            await init_db()
    finally:
        conn._engine = old_engine
