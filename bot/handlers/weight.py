from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, or_f
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from bot.database import crud
from bot.handlers.utils import parse_float
from bot.keyboards import BTN_WEIGHT
from bot.runtime import get_app_context

router = Router()


class WeightStates(StatesGroup):
    waiting_value = State()


@router.message(or_f(Command("weight"), F.text == BTN_WEIGHT))
async def weight_command(message: Message, state: FSMContext) -> None:
    await state.set_state(WeightStates.waiting_value)
    await message.answer("Введи текущий вес в кг (например: 72.5).")


@router.message(WeightStates.waiting_value)
async def weight_value(message: Message, state: FSMContext) -> None:
    if not message.from_user:
        return
    value = parse_float(message.text or "")
    if value is None or value < 30 or value > 350:
        await message.answer("Введите корректный вес от 30 до 350 кг.")
        return
    ctx = get_app_context()
    async with ctx.sessionmaker() as session:
        user = await crud.get_user(session, message.from_user.id)
        if user is None:
            await message.answer("Сначала пройди /start.")
            await state.clear()
            return
        await crud.add_weight_log(session, message.from_user.id, value)
        history = await crud.get_weight_logs(session, message.from_user.id, limit=2)

    delta = value - user.weight_start_kg
    trend = ""
    if len(history) >= 2:
        trend_val = history[0].weight_kg - history[1].weight_kg
        trend = f"\nИзменение с прошлого взвешивания: {trend_val:+.1f} кг"
    await message.answer(
        f"Вес сохранен: {value:.1f} кг.\n"
        f"Разница со стартовым: {delta:+.1f} кг{trend}"
    )
    await state.clear()

