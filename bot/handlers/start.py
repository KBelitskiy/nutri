from __future__ import annotations

from zoneinfo import ZoneInfo, available_timezones

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
    timezone = State()
    timezone_custom = State()


GENDER_MAP = {
    "мужской": "male",
    "женский": "female",
    "male": "male",
    "female": "female",
}
ACTIVITY_MAP = {
    "низкая": "low",
    "лёгкая": "light",
    "легкая": "light",
    "средняя": "moderate",
    "высокая": "high",
    "очень высокая": "very_high",
    "low": "low",
    "light": "light",
    "moderate": "moderate",
    "high": "high",
    "very_high": "very_high",
}
GOAL_MAP = {
    "похудеть": "lose",
    "поддерживать вес": "maintain",
    "набрать массу": "gain",
    "lose": "lose",
    "maintain": "maintain",
    "gain": "gain",
}
TIMEZONE_MAP = {
    "Москва (UTC+3)": "Europe/Moscow",
    "Екатеринбург (UTC+5)": "Asia/Yekaterinburg",
    "Новосибирск (UTC+7)": "Asia/Novosibirsk",
    "Владивосток (UTC+10)": "Asia/Vladivostok",
    "Другой": None,
}

GENDER_KB = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="Мужской"), KeyboardButton(text="Женский")]],
    resize_keyboard=True,
)
ACTIVITY_KB = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Низкая"), KeyboardButton(text="Лёгкая")],
        [KeyboardButton(text="Средняя"), KeyboardButton(text="Высокая")],
        [KeyboardButton(text="Очень высокая")],
    ],
    resize_keyboard=True,
)
GOAL_KB = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="Похудеть"),
            KeyboardButton(text="Поддерживать вес"),
            KeyboardButton(text="Набрать массу"),
        ]
    ],
    resize_keyboard=True,
)
TIMEZONE_KB = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Москва (UTC+3)"), KeyboardButton(text="Екатеринбург (UTC+5)")],
        [KeyboardButton(text="Новосибирск (UTC+7)"), KeyboardButton(text="Владивосток (UTC+10)")],
        [KeyboardButton(text="Другой")],
    ],
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
        "Привет! Я NutriBot. Давай заполним профиль.\nУкажи пол:",
        reply_markup=GENDER_KB,
    )


@router.message(OnboardingStates.gender)
async def onboarding_gender(message: Message, state: FSMContext) -> None:
    value = (message.text or "").strip().lower()
    normalized = GENDER_MAP.get(value)
    if normalized is None:
        await message.answer("Выбери вариант кнопкой: Мужской или Женский.")
        return
    await state.update_data(gender=normalized)
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
    normalized = ACTIVITY_MAP.get(value)
    if normalized is None:
        await message.answer("Выбери уровень активности кнопкой.")
        return
    await state.update_data(activity_level=normalized)
    await state.set_state(OnboardingStates.goal)
    await message.answer("Какая у тебя цель?", reply_markup=GOAL_KB)


@router.message(OnboardingStates.goal)
async def onboarding_goal(message: Message, state: FSMContext) -> None:
    goal_text = (message.text or "").strip().lower()
    goal = GOAL_MAP.get(goal_text)
    if goal is None:
        await message.answer("Выбери цель кнопкой.")
        return

    data = await state.get_data()
    data["goal"] = goal
    await state.update_data(goal=goal)
    await state.set_state(OnboardingStates.timezone)
    await message.answer(
        "Выбери свой часовой пояс:",
        reply_markup=TIMEZONE_KB,
    )


async def _complete_onboarding(
    message: Message,
    state: FSMContext,
    data: dict[str, object],
    timezone_name: str,
) -> None:
    if not message.from_user:
        return

    targets = calculate_daily_targets(
        gender=str(data["gender"]),
        age=int(data["age"]),
        height_cm=float(data["height_cm"]),
        weight_kg=float(data["weight_start_kg"]),
        activity_level=str(data["activity_level"]),
        goal=str(data["goal"]),
    )
    payload = {
        "telegram_id": message.from_user.id,
        "username": message.from_user.username,
        "gender": data["gender"],
        "age": int(data["age"]),
        "height_cm": float(data["height_cm"]),
        "weight_start_kg": float(data["weight_start_kg"]),
        "activity_level": data["activity_level"],
        "goal": data["goal"],
        "timezone": timezone_name,
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


@router.message(OnboardingStates.timezone)
async def onboarding_timezone(message: Message, state: FSMContext) -> None:
    selected = (message.text or "").strip()
    if selected not in TIMEZONE_MAP:
        await message.answer("Выбери часовой пояс кнопкой или нажми «Другой».")
        return
    mapped = TIMEZONE_MAP[selected]
    if mapped is None:
        await state.set_state(OnboardingStates.timezone_custom)
        await message.answer(
            "Введи часовой пояс в формате IANA, например Europe/Moscow:",
            reply_markup=ReplyKeyboardRemove(),
        )
        return
    await state.update_data(timezone=mapped)
    data = await state.get_data()
    await _complete_onboarding(message, state, data, mapped)


@router.message(OnboardingStates.timezone_custom)
async def onboarding_timezone_custom(message: Message, state: FSMContext) -> None:
    value = (message.text or "").strip()
    if value not in available_timezones():
        await message.answer("Неизвестный часовой пояс. Пример: Europe/Moscow")
        return
    try:
        ZoneInfo(value)
    except Exception:  # noqa: BLE001
        await message.answer("Не удалось распознать часовой пояс. Попробуй снова.")
        return
    await state.update_data(timezone=value)
    data = await state.get_data()
    await _complete_onboarding(message, state, data, value)


@router.message(F.text == BTN_BACK)
async def back_to_menu(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Выбери действие.", reply_markup=MAIN_MENU_KB)


@router.message(F.text == "/cancel")
async def cancel_fsm(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Операция отменена.")

