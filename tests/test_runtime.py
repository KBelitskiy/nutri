"""Тесты runtime контекста (bot.runtime)."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from bot.runtime import AppContext, get_app_context, set_app_context


def test_set_and_get_app_context() -> None:
    ctx = MagicMock(spec=AppContext)
    set_app_context(ctx)
    assert get_app_context() is ctx


def test_get_app_context_raises_when_not_set() -> None:
    set_app_context(None)  # type: ignore[arg-type]
    try:
        with pytest.raises(RuntimeError, match="not initialized"):
            get_app_context()
    finally:
        set_app_context(MagicMock(spec=AppContext))


def test_app_context_has_expected_attrs() -> None:
    settings = MagicMock()
    sessionmaker = MagicMock()
    agent = MagicMock()
    ctx = AppContext(settings=settings, sessionmaker=sessionmaker, agent=agent)
    assert ctx.settings is settings
    assert ctx.sessionmaker is sessionmaker
    assert ctx.agent is agent
