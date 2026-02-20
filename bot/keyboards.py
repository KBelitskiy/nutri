"""Клавиатуры бота: главное меню, подменю профиля и тексты кнопок для фильтров."""
from __future__ import annotations

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

# Тексты кнопок главного меню (с эмодзи)
BTN_TODAY = "📊 Сводка за сегодня"
BTN_PROFILE = "👤 Профиль"
BTN_STATS = "📈 Статистика"
BTN_HISTORY = "📋 Отредактировать записанное"
BTN_SUGGEST = "💡 Рекомендации"
BTN_WATER_QUICK = "💧 +250мл воды"
BTN_LEAGUE_TODAY = "🏁 Лига: сегодня"
BTN_LEAGUE_WEEK = "🏁 Лига: неделя"

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
    BTN_WATER_QUICK,
    BTN_WEIGHT,
    BTN_HELP,
    BTN_RESET,
    BTN_BACK,
)

# Главное меню: Сегодня, Статистика, Вес, Рекомендации, Профиль
MAIN_MENU_KB = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text=BTN_TODAY), KeyboardButton(text=BTN_STATS)],
        [KeyboardButton(text=BTN_WEIGHT), KeyboardButton(text=BTN_SUGGEST)],
        [KeyboardButton(text=BTN_WATER_QUICK)],
        [KeyboardButton(text=BTN_PROFILE)],
    ],
    resize_keyboard=True,
)

# Подменю при нажатии «Профиль»: Отредактировать записанное, Помощь, Сброс данных, В меню
PROFILE_SUBMENU_KB = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text=BTN_WEIGHT), KeyboardButton(text=BTN_HISTORY)],
        [KeyboardButton(text=BTN_HELP)],
        [KeyboardButton(text=BTN_RESET)],
        [KeyboardButton(text=BTN_BACK)],
    ],
    resize_keyboard=True,
)

# Меню в групповом чате: ручной запуск лиговых сводок
GROUP_MENU_KB = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text=BTN_LEAGUE_TODAY), KeyboardButton(text=BTN_LEAGUE_WEEK)],
    ],
    resize_keyboard=True,
)
