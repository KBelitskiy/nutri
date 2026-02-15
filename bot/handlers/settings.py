from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, or_f
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot.database import crud
from bot.handlers.utils import parse_float, parse_int
from bot.keyboards import BTN_PROFILE, BTN_RESET, MAIN_MENU_KB, PROFILE_SUBMENU_KB
from bot.runtime import get_app_context
from bot.services.nutrition import calculate_daily_targets

router = Router()


@router.message(or_f(Command("profile"), F.text == BTN_PROFILE))
async def profile_update(message: Message) -> None:
    if not message.from_user or not message.text:
        return
    parts = message.text.split(maxsplit=2)
    ctx = get_app_context()
    async with ctx.sessionmaker() as session:
        user = await crud.get_user(session, message.from_user.id)
        if user is None:
            await message.answer("Сначала пройди онбординг: /start")
            return
        if len(parts) != 3:
            await message.answer(
                "Профиль:\n"
                f"Пол: {user.gender}\nВозраст: {user.age}\nРост: {user.height_cm} см\n"
                f"Стартовый вес: {user.weight_start_kg} кг\nАктивность: {user.activity_level}\nЦель: {user.goal}\n\n"
                "Обновление: /profile <field> <value>\n"
                "Поля: gender, age, height_cm, weight_start_kg, activity_level, goal",
                reply_markup=PROFILE_SUBMENU_KB,
            )
            return
        _, field, raw_value = parts

        if field == "gender":
            value = raw_value.lower()
            if value not in {"male", "female"}:
                await message.answer("gender должен быть male или female")
                return
            user.gender = value
        elif field == "age":
            value = parse_int(raw_value)
            if value is None or value < 10 or value > 100:
                await message.answer("Возраст должен быть в диапазоне 10..100")
                return
            user.age = value
        elif field == "height_cm":
            value = parse_float(raw_value)
            if value is None or value < 100 or value > 250:
                await message.answer("Рост должен быть в диапазоне 100..250")
                return
            user.height_cm = value
        elif field == "weight_start_kg":
            value = parse_float(raw_value)
            if value is None or value < 30 or value > 350:
                await message.answer("Вес должен быть в диапазоне 30..350")
                return
            user.weight_start_kg = value
        elif field == "activity_level":
            value = raw_value.lower()
            if value not in {"low", "light", "moderate", "high", "very_high"}:
                await message.answer("activity_level: low/light/moderate/high/very_high")
                return
            user.activity_level = value
        elif field == "goal":
            value = raw_value.lower()
            if value not in {"lose", "maintain", "gain"}:
                await message.answer("goal: lose/maintain/gain")
                return
            user.goal = value
        else:
            await message.answer("Неизвестное поле.")
            return

        targets = calculate_daily_targets(
            gender=user.gender,
            age=user.age,
            height_cm=user.height_cm,
            weight_kg=user.weight_start_kg,
            activity_level=user.activity_level,  # type: ignore[arg-type]
            goal=user.goal,  # type: ignore[arg-type]
        )
        user.daily_calories_target = targets["daily_calories_target"]
        user.daily_protein_target = targets["daily_protein_target"]
        user.daily_fat_target = targets["daily_fat_target"]
        user.daily_carbs_target = targets["daily_carbs_target"]
        await session.commit()

    await message.answer("Профиль обновлен и цели пересчитаны.")


@router.message(or_f(Command("reset"), F.text == BTN_RESET))
async def reset_command(message: Message) -> None:
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Да, удалить", callback_data="reset_yes"),
                InlineKeyboardButton(text="Нет", callback_data="reset_no"),
            ]
        ]
    )
    await message.answer("Удалить все данные профиля, питания и веса?", reply_markup=kb)


@router.callback_query(lambda c: c.data in {"reset_yes", "reset_no"})
async def reset_confirm(callback) -> None:  # type: ignore[no-untyped-def]
    if callback.data == "reset_no":
        await callback.message.answer("Удаление отменено.")
        await callback.answer()
        return
    if not callback.from_user:
        await callback.answer()
        return
    ctx = get_app_context()
    async with ctx.sessionmaker() as session:
        await crud.delete_user_data(session, callback.from_user.id)
    await callback.message.answer(
        "Данные удалены. Можешь начать заново: /start",
        reply_markup=MAIN_MENU_KB,
    )
    await callback.answer()

