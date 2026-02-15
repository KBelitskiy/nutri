"""Клавиатуры бота: главное меню, подменю профиля и тексты кнопок для фильтров."""
from __future__ import annotations

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

# Тексты кнопок главного меню (с эмодзи)
BTN_TODAY = "📊 Сегодня"
BTN_PROFILE = "👤 Профиль"
BTN_STATS = "📈 Статистика"
BTN_HISTORY = "📋 История"
BTN_SUGGEST = "💡 Рекомендации"

# Подменю «Профиль»
BTN_WEIGHT = "⚖️ Вес"
BTN_HELP = "❓ Помощь"
BTN_RESET = "🗑 Сброс данных"
BTN_BACK = "◀️ В меню"

# Все тексты кнопок (чтобы не отправлять их агенту)
MAIN_MENU_BUTTONS = (
    BTN_TODAY,
    BTN_PROFILE,
    BTN_STATS,
    BTN_HISTORY,
    BTN_SUGGEST,
    BTN_WEIGHT,
    BTN_HELP,
    BTN_RESET,
    BTN_BACK,
)

# Главное меню: Сегодня, Статистика, История, Рекомендации, Профиль
MAIN_MENU_KB = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text=BTN_TODAY), KeyboardButton(text=BTN_STATS)],
        [KeyboardButton(text=BTN_HISTORY), KeyboardButton(text=BTN_SUGGEST)],
        [KeyboardButton(text=BTN_PROFILE)],
    ],
    resize_keyboard=True,
)

# Подменю при нажатии «Профиль»: Вес, Помощь, Сброс данных, В меню
PROFILE_SUBMENU_KB = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text=BTN_WEIGHT), KeyboardButton(text=BTN_HELP)],
        [KeyboardButton(text=BTN_RESET)],
        [KeyboardButton(text=BTN_BACK)],
    ],
    resize_keyboard=True,
)
