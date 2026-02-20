from __future__ import annotations

from dataclasses import dataclass

from aiogram.types import InlineKeyboardMarkup


@dataclass(slots=True)
class PendingPhoto:
    content: bytes
    filename: str
    caption: str | None = None
    keyboard: InlineKeyboardMarkup | None = None


_PENDING_BY_USER: dict[int, list[PendingPhoto]] = {}


def add_pending_photo(user_id: int, photo: PendingPhoto) -> None:
    _PENDING_BY_USER.setdefault(user_id, []).append(photo)


def pop_pending_photos(user_id: int) -> list[PendingPhoto]:
    return _PENDING_BY_USER.pop(user_id, [])
