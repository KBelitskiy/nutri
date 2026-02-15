from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, or_f
from aiogram.types import Message

from bot.database import crud
from bot.keyboards import BTN_SUGGEST
from bot.runtime import get_app_context

router = Router()


@router.message(or_f(Command("suggest"), F.text == BTN_SUGGEST))
async def suggest(message: Message) -> None:
    if not message.from_user:
        return
    ctx = get_app_context()
    async with ctx.sessionmaker() as session:
        user = await crud.get_user(session, message.from_user.id)
        if user is None:
            await message.answer("Сначала пройди /start.")
            return
        consumed = await crud.get_meal_summary_for_day(session, message.from_user.id)
        meals_today = await crud.get_meals_for_day(session, message.from_user.id)

    calories_left = max(0.0, user.daily_calories_target - consumed["calories"])
    protein_left = max(0.0, user.daily_protein_target - consumed["protein_g"])
    fat_left = max(0.0, user.daily_fat_target - consumed["fat_g"])
    carbs_left = max(0.0, user.daily_carbs_target - consumed["carbs_g"])

    profile_block = (
        "Профиль пользователя:\n"
        f"- Пол: {user.gender}, возраст: {user.age} лет, рост: {user.height_cm} см, вес: {user.weight_start_kg} кг\n"
        f"- Уровень активности: {user.activity_level}, цель: {user.goal}\n"
        f"- Дневные цели: {user.daily_calories_target:.0f} ккал, "
        f"Б {user.daily_protein_target:.0f} г, Ж {user.daily_fat_target:.0f} г, У {user.daily_carbs_target:.0f} г\n"
    )
    stats_block = (
        "Потребление за сегодня:\n"
        f"- Съедено: {consumed['calories']:.0f} ккал, Б {consumed['protein_g']:.0f} г, "
        f"Ж {consumed['fat_g']:.0f} г, У {consumed['carbs_g']:.0f} г\n"
        f"- Осталось до нормы: {calories_left:.0f} ккал, Б {protein_left:.0f} г, "
        f"Ж {fat_left:.0f} г, У {carbs_left:.0f} г\n"
    )
    if meals_today:
        meals_lines = [
            f"  • {m.description}: {m.calories:.0f} ккал, Б {m.protein_g:.0f} / Ж {m.fat_g:.0f} / У {m.carbs_g:.0f} г"
            for m in meals_today
        ]
        meals_block = "Приёмы пищи за сегодня:\n" + "\n".join(meals_lines) + "\n"
    else:
        meals_block = "Приёмов пищи за сегодня пока нет.\n"

    prompt = (
        "Предложи 3 варианта, чем добрать дневную норму, варианты могут быть как блюдами так и просто продуктами. Если это готовое блюдо - приложи рецепт блюда с указанием всех ингредиентов и их количества, если это продукт - просто опиши продукт и указание количества в граммах. "
        "Учитывай остаток калорий и БЖУ, профиль и уже съеденное, твои рекомендации должны добивать дневную норму до 100% .\n\n"
        f"{profile_block}\n{stats_block}\n{meals_block}\n"
        "Дай конкретные варианты блюд/перекусов с примерными порциями и КБЖУ."
    )
    try:
        answer = await ctx.agent.ask(prompt, use_tools=False)
    except Exception:  # noqa: BLE001
        await message.answer("Не удалось получить рекомендацию, попробуй позже.")
        return
    await message.answer(answer)

