from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, or_f
from aiogram.types import Message

from bot.keyboards import BTN_HELP

router = Router()


@router.message(or_f(Command("help"), F.text == BTN_HELP))
async def help_command(message: Message) -> None:
    await message.answer(
        "Меню бота:\n\n"
        "📊 Сегодня — сводка за день\n"
        "📈 Статистика — за период (/stats day | week | month)\n"
        "📋 История — приёмы пищи за сегодня (можно удалить)\n"
        "💡 Рекомендации — чем добить норму\n"
        "👤 Профиль — данные и цели; внутри:\n"
        "  ⚖️ Вес, ❓ Помощь, 🗑 Сброс данных, ◀️ В меню\n"
        "Редактирование профиля: /profile <поле> <значение>\n\n"
        "В группе для быстрой проверки: /league_today и /league_week\n\n"
        "Можно писать текстом что съел или отправить фото еды."
    )

