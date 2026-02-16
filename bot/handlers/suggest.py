from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, or_f
from aiogram.types import Message
from zoneinfo import ZoneInfo

from bot.database import crud
from bot.keyboards import BTN_SUGGEST
from bot.prompts import (
    meals_block as prompts_meals_block,
    suggest_profile_block as prompts_profile_block,
    suggest_stats_block as prompts_stats_block,
    suggest_prompt,
)
from bot.runtime import get_app_context

router = Router()


@router.message(or_f(Command("suggest"), F.text == BTN_SUGGEST))
async def suggest(message: Message) -> None:
    if not message.from_user:
        return
    ctx = get_app_context()
    tz = ZoneInfo(ctx.settings.league_report_timezone)
    async with ctx.sessionmaker() as session:
        user = await crud.get_user(session, message.from_user.id)
        if user is None:
            await message.answer("Сначала пройди /start.")
            return
        consumed = await crud.get_meal_summary_for_day(
            session, message.from_user.id, timezone=tz
        )
        meals_today = await crud.get_meals_for_day(session, message.from_user.id, timezone=tz)

    calories_left = max(0.0, user.daily_calories_target - consumed["calories"])
    protein_left = max(0.0, user.daily_protein_target - consumed["protein_g"])
    fat_left = max(0.0, user.daily_fat_target - consumed["fat_g"])
    carbs_left = max(0.0, user.daily_carbs_target - consumed["carbs_g"])

    profile_block = prompts_profile_block(
        gender=user.gender,
        age=user.age,
        height_cm=user.height_cm,
        weight_start_kg=user.weight_start_kg,
        activity_level=user.activity_level,
        goal=user.goal,
        daily_calories_target=user.daily_calories_target,
        daily_protein_target=user.daily_protein_target,
        daily_fat_target=user.daily_fat_target,
        daily_carbs_target=user.daily_carbs_target,
    )
    stats_block = prompts_stats_block(
        consumed_calories=consumed["calories"],
        consumed_protein=consumed["protein_g"],
        consumed_fat=consumed["fat_g"],
        consumed_carbs=consumed["carbs_g"],
        calories_left=calories_left,
        protein_left=protein_left,
        fat_left=fat_left,
        carbs_left=carbs_left,
    )
    meals_lines = [
        f"  • {m.description}: {m.calories:.0f} ккал, Б {m.protein_g:.0f} / Ж {m.fat_g:.0f} / У {m.carbs_g:.0f} г"
        for m in meals_today
    ]
    meals_block = prompts_meals_block(meals_lines)

    prompt = suggest_prompt(
        profile_block=profile_block,
        stats_block=stats_block,
        meals_block=meals_block,
    )
    try:
        answer = await ctx.agent.ask(prompt, use_tools=False)
    except Exception:  # noqa: BLE001
        await message.answer("Не удалось получить рекомендацию, попробуй позже.")
        return
    await message.answer(answer)

