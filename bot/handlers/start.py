from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup, ReplyKeyboardRemove

from bot.database import crud
from bot.handlers.utils import parse_float, parse_int
from bot.keyboards import BTN_BACK, MAIN_MENU_KB
from bot.runtime import get_app_context
from bot.services.nutrition import calculate_daily_targets

router = Router()


class OnboardingStates(StatesGroup):
    gender = State()
    age = State()
    height = State()
    weight = State()
    activity = State()
    goal = State()


GENDER_KB = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="male"), KeyboardButton(text="female")]],
    resize_keyboard=True,
)
ACTIVITY_KB = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="low"), KeyboardButton(text="light")],
        [KeyboardButton(text="moderate"), KeyboardButton(text="high"), KeyboardButton(text="very_high")],
    ],
    resize_keyboard=True,
)
GOAL_KB = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="lose"), KeyboardButton(text="maintain"), KeyboardButton(text="gain")]],
    resize_keyboard=True,
)


@router.message(CommandStart())
async def command_start(message: Message, state: FSMContext) -> None:
    ctx = get_app_context()
    if not message.from_user:
        return
    async with ctx.sessionmaker() as session:
        user = await crud.get_user(session, message.from_user.id)

    if user:
        await message.answer(
            "С возвращением! Выбери действие в меню ниже.",
            reply_markup=MAIN_MENU_KB,
        )
        await state.clear()
        return

    await state.set_state(OnboardingStates.gender)
    await message.answer(
        "Привет! Я NutriBot. Давай заполним профиль.\nУкажи пол: male / female",
        reply_markup=GENDER_KB,
    )


@router.message(OnboardingStates.gender)
async def onboarding_gender(message: Message, state: FSMContext) -> None:
    value = (message.text or "").strip().lower()
    if value not in {"male", "female"}:
        await message.answer("Введите `male` или `female`.")
        return
    await state.update_data(gender=value)
    await state.set_state(OnboardingStates.age)
    await message.answer("Возраст (полных лет)?", reply_markup=ReplyKeyboardRemove())


@router.message(OnboardingStates.age)
async def onboarding_age(message: Message, state: FSMContext) -> None:
    age = parse_int(message.text or "")
    if age is None or age < 10 or age > 100:
        await message.answer("Введите корректный возраст от 10 до 100.")
        return
    await state.update_data(age=age)
    await state.set_state(OnboardingStates.height)
    await message.answer("Рост в сантиметрах?")


@router.message(OnboardingStates.height)
async def onboarding_height(message: Message, state: FSMContext) -> None:
    height = parse_float(message.text or "")
    if height is None or height < 100 or height > 250:
        await message.answer("Введите корректный рост от 100 до 250 см.")
        return
    await state.update_data(height_cm=height)
    await state.set_state(OnboardingStates.weight)
    await message.answer("Текущий вес в кг?")


@router.message(OnboardingStates.weight)
async def onboarding_weight(message: Message, state: FSMContext) -> None:
    weight = parse_float(message.text or "")
    if weight is None or weight < 30 or weight > 350:
        await message.answer("Введите корректный вес от 30 до 350 кг.")
        return
    await state.update_data(weight_start_kg=weight)
    await state.set_state(OnboardingStates.activity)
    await message.answer("Уровень активности: low / light / moderate / high / very_high", reply_markup=ACTIVITY_KB)


@router.message(OnboardingStates.activity)
async def onboarding_activity(message: Message, state: FSMContext) -> None:
    value = (message.text or "").strip().lower()
    if value not in {"low", "light", "moderate", "high", "very_high"}:
        await message.answer("Введите одно из: low, light, moderate, high, very_high.")
        return
    await state.update_data(activity_level=value)
    await state.set_state(OnboardingStates.goal)
    await message.answer("Цель: lose / maintain / gain", reply_markup=GOAL_KB)


@router.message(OnboardingStates.goal)
async def onboarding_goal(message: Message, state: FSMContext) -> None:
    goal = (message.text or "").strip().lower()
    if goal not in {"lose", "maintain", "gain"}:
        await message.answer("Введите одну цель: lose / maintain / gain.")
        return

    data = await state.get_data()
    data["goal"] = goal
    if not message.from_user:
        return

    targets = calculate_daily_targets(
        gender=data["gender"],
        age=int(data["age"]),
        height_cm=float(data["height_cm"]),
        weight_kg=float(data["weight_start_kg"]),
        activity_level=data["activity_level"],
        goal=goal,
    )
    payload = {
        "telegram_id": message.from_user.id,
        "username": message.from_user.username,
        "gender": data["gender"],
        "age": int(data["age"]),
        "height_cm": float(data["height_cm"]),
        "weight_start_kg": float(data["weight_start_kg"]),
        "activity_level": data["activity_level"],
        "goal": goal,
        **targets,
    }

    ctx = get_app_context()
    async with ctx.sessionmaker() as session:
        user = await crud.create_or_update_user(session, payload)
        await crud.add_weight_log(session, user.telegram_id, user.weight_start_kg)

    await state.clear()
    await message.answer(
        "Готово, профиль сохранен.\n"
        f"Твои цели: {user.daily_calories_target:.1f} ккал, "
        f"Б {user.daily_protein_target:.1f} г, Ж {user.daily_fat_target:.1f} г, "
        f"У {user.daily_carbs_target:.1f} г.\n"
        "Выбери действие в меню или отправь текст с едой, например: гречка 200 г и куриная грудка.",
        reply_markup=MAIN_MENU_KB,
    )


@router.message(F.text == BTN_BACK)
async def back_to_menu(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Выбери действие.", reply_markup=MAIN_MENU_KB)


@router.message(F.text == "/cancel")
async def cancel_fsm(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Операция отменена.")

