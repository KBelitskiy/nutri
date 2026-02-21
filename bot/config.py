from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv


@dataclass(slots=True)
class Settings:
    telegram_bot_token: str
    openai_api_key: str
    database_url: str
    openai_model_text: str
    openai_model_vision: str
    openai_base_url: str | None
    openai_max_requests_per_minute: int
    league_report_timezone: str


def _persistent_data_dir() -> Path | None:
    """Возвращает /data если она смонтирована (persistent mount на Amvera), иначе None."""
    data_dir = Path("/data")
    return data_dir if data_dir.exists() else None


def _default_sqlite_url() -> str:
    # Если /data существует (persistent mount на Amvera) — всегда используем его,
    # чтобы база не терялась при пересборке контейнера.
    data_dir = _persistent_data_dir()
    if data_dir is not None:
        path = data_dir / "nutri.db"
    else:
        sqlite_path = os.getenv("SQLITE_PATH", "./nutri.db")
        path = Path(sqlite_path).expanduser().resolve()
    return f"sqlite+aiosqlite:///{path}"


def load_settings() -> Settings:
    load_dotenv()
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    openai_key = os.getenv("OPENAI_API_KEY", "").strip()
    db_url = os.getenv("DATABASE_URL", "").strip() or _default_sqlite_url()
    text_model = os.getenv("OPENAI_MODEL_TEXT", "gpt-4o-mini").strip()
    vision_model = os.getenv("OPENAI_MODEL_VISION", "gpt-4o-mini").strip()
    base_url = (
        os.getenv("OPENAI_BASE_URL", "").strip()
        or os.getenv("BASE_URL", "").strip()
        or os.getenv("base_url", "").strip()
        or None
    )
    rpm = int(os.getenv("OPENAI_MAX_REQUESTS_PER_MINUTE", "20"))
    league_tz = os.getenv("LEAGUE_REPORT_TIMEZONE", "").strip()
    if not league_tz:
        local_tz = datetime.now().astimezone().tzinfo
        league_tz = str(getattr(local_tz, "key", "")) or "UTC"

    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN is required")
    if not openai_key:
        raise ValueError("OPENAI_API_KEY is required")

    return Settings(
        telegram_bot_token=token,
        openai_api_key=openai_key,
        database_url=db_url,
        openai_model_text=text_model,
        openai_model_vision=vision_model,
        openai_base_url=base_url,
        openai_max_requests_per_minute=rpm,
        league_report_timezone=league_tz,
    )

