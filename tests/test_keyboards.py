"""Тесты клавиатур бота (bot.keyboards)."""
from __future__ import annotations

import pytest

from bot.keyboards import (
    BTN_BACK,
    BTN_HELP,
    BTN_HISTORY,
    BTN_PROFILE,
    BTN_RESET,
    BTN_STATS,
    BTN_SUGGEST,
    BTN_TODAY,
    BTN_WEIGHT,
    MAIN_MENU_BUTTONS,
    MAIN_MENU_KB,
    PROFILE_SUBMENU_KB,
)


def test_main_menu_buttons_defined() -> None:
    assert BTN_TODAY in MAIN_MENU_BUTTONS
    assert BTN_STATS in MAIN_MENU_BUTTONS
    assert BTN_HISTORY in MAIN_MENU_BUTTONS
    assert BTN_SUGGEST in MAIN_MENU_BUTTONS
    assert BTN_PROFILE in MAIN_MENU_BUTTONS
    assert BTN_WEIGHT in MAIN_MENU_BUTTONS
    assert BTN_HELP in MAIN_MENU_BUTTONS
    assert BTN_RESET in MAIN_MENU_BUTTONS
    assert BTN_BACK in MAIN_MENU_BUTTONS


def test_main_menu_kb_has_rows() -> None:
    assert hasattr(MAIN_MENU_KB, "keyboard")
    rows = MAIN_MENU_KB.keyboard
    assert len(rows) >= 1
    all_texts = []
    for row in rows:
        for btn in row:
            all_texts.append(btn.text)
    assert BTN_TODAY in all_texts
    assert BTN_STATS in all_texts
    assert BTN_PROFILE in all_texts


def test_profile_submenu_kb_has_weight_help_reset_back() -> None:
    rows = PROFILE_SUBMENU_KB.keyboard
    all_texts = [btn.text for row in rows for btn in row]
    assert BTN_WEIGHT in all_texts
    assert BTN_HELP in all_texts
    assert BTN_RESET in all_texts
    assert BTN_BACK in all_texts


def test_main_menu_resize_keyboard() -> None:
    assert MAIN_MENU_KB.resize_keyboard is True


def test_profile_submenu_resize_keyboard() -> None:
    assert PROFILE_SUBMENU_KB.resize_keyboard is True
