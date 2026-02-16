"""Тесты конфигурации (bot.config)."""
from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from bot.config import Settings, load_settings, _default_sqlite_url


class TestDefaultSqliteUrl:
    def test_returns_sqlite_aiosqlite_path(self) -> None:
        with patch.dict(os.environ, {"SQLITE_PATH": "/tmp/nutri.db"}, clear=False):
            url = _default_sqlite_url()
        assert url.startswith("sqlite+aiosqlite:///")
        assert "nutri" in url or "tmp" in url

    def test_uses_env_sqlite_path(self) -> None:
        with patch.dict(os.environ, {"SQLITE_PATH": "/custom/path/db.sqlite"}, clear=False):
            url = _default_sqlite_url()
        assert "custom" in url or "path" in url or "db" in url


class TestLoadSettings:
    def test_raises_without_telegram_token(self) -> None:
        with patch.dict(
            os.environ,
            {"TELEGRAM_BOT_TOKEN": "", "OPENAI_API_KEY": "sk-fake"},
            clear=False,
        ):
            with patch("bot.config.load_dotenv"):
                with pytest.raises(ValueError, match="TELEGRAM_BOT_TOKEN"):
                    load_settings()

    def test_raises_without_openai_key(self) -> None:
        with patch.dict(
            os.environ,
            {"TELEGRAM_BOT_TOKEN": "123:abc", "OPENAI_API_KEY": ""},
            clear=False,
        ):
            with patch("bot.config.load_dotenv"):
                with pytest.raises(ValueError, match="OPENAI_API_KEY"):
                    load_settings()

    def test_returns_settings_with_defaults(self) -> None:
        with patch.dict(
            os.environ,
            {
                "TELEGRAM_BOT_TOKEN": "123:abc",
                "OPENAI_API_KEY": "sk-fake",
                "DATABASE_URL": "",
            },
            clear=False,
        ):
            with patch("bot.config.load_dotenv"):
                with patch("bot.config._default_sqlite_url", return_value="sqlite+aiosqlite:///./nutri.db"):
                    s = load_settings()
        assert s.telegram_bot_token == "123:abc"
        assert s.openai_api_key == "sk-fake"
        assert s.database_url == "sqlite+aiosqlite:///./nutri.db"
        assert s.openai_model_text == "gpt-4o-mini"
        assert s.openai_model_vision == "gpt-4o-mini"
        assert s.openai_base_url is None
        assert s.openai_max_requests_per_minute == 20
        assert isinstance(s.league_report_timezone, str)
        assert s.league_report_timezone

    def test_uses_env_database_url_when_set(self) -> None:
        with patch.dict(
            os.environ,
            {
                "TELEGRAM_BOT_TOKEN": "123:abc",
                "OPENAI_API_KEY": "sk-fake",
                "DATABASE_URL": "postgresql+asyncpg://localhost/nutri",
            },
            clear=False,
        ):
            with patch("bot.config.load_dotenv"):
                s = load_settings()
        assert s.database_url == "postgresql+asyncpg://localhost/nutri"

    def test_uses_env_model_and_rpm(self) -> None:
        with patch.dict(
            os.environ,
            {
                "TELEGRAM_BOT_TOKEN": "123:abc",
                "OPENAI_API_KEY": "sk-fake",
                "OPENAI_MODEL_TEXT": "gpt-4o",
                "OPENAI_MODEL_VISION": "gpt-4o",
                "OPENAI_MAX_REQUESTS_PER_MINUTE": "10",
            },
            clear=False,
        ):
            with patch("bot.config.load_dotenv"):
                with patch("bot.config._default_sqlite_url", return_value="sqlite:///x.db"):
                    s = load_settings()
        assert s.openai_model_text == "gpt-4o"
        assert s.openai_model_vision == "gpt-4o"
        assert s.openai_max_requests_per_minute == 10

    def test_uses_env_league_timezone(self) -> None:
        with patch.dict(
            os.environ,
            {
                "TELEGRAM_BOT_TOKEN": "123:abc",
                "OPENAI_API_KEY": "sk-fake",
                "LEAGUE_REPORT_TIMEZONE": "Europe/Moscow",
            },
            clear=False,
        ):
            with patch("bot.config.load_dotenv"):
                s = load_settings()
        assert s.league_report_timezone == "Europe/Moscow"

    def test_uses_env_openai_base_url_from_lowercase_key(self) -> None:
        with patch.dict(
            os.environ,
            {
                "TELEGRAM_BOT_TOKEN": "123:abc",
                "OPENAI_API_KEY": "sk-fake",
                "base_url": "https://api.proxyapi.ru/openai/v1",
            },
            clear=False,
        ):
            with patch("bot.config.load_dotenv"):
                s = load_settings()
        assert s.openai_base_url == "https://api.proxyapi.ru/openai/v1"


class TestSettingsDataclass:
    def test_settings_instance_has_expected_fields(self) -> None:
        s = Settings(
            telegram_bot_token="t",
            openai_api_key="k",
            database_url="sqlite:///",
            openai_model_text="gpt-4o-mini",
            openai_model_vision="gpt-4o-mini",
            openai_base_url=None,
            openai_max_requests_per_minute=20,
            league_report_timezone="UTC",
        )
        assert s.telegram_bot_token == "t"
        assert s.openai_api_key == "k"
        assert s.openai_max_requests_per_minute == 20
