from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, or_f, StateFilter
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot.database import crud

# История диалога с агентом: user_id -> список пар (сообщение пользователя, ответ ассистента), макс. 10 пар
CONVERSATION_HISTORY: dict[int, list[tuple[str, str]]] = {}
MAX_HISTORY_PAIRS = 10
from bot.handlers.start import OnboardingStates
from bot.handlers.weight import WeightStates
from bot.handlers.utils import progress_text
from bot.keyboards import BTN_HISTORY, MAIN_MENU_BUTTONS
from bot.runtime import get_app_context
from bot.services.vision import analyze_meal_photo

router = Router()


@router.message(or_f(Command("history"), F.text == BTN_HISTORY))
async def history(message: Message) -> None:
    if not message.from_user:
        return
    ctx = get_app_context()
    async with ctx.sessionmaker() as session:
        user = await crud.get_user(session, message.from_user.id)
        if user is None:
            await message.answer("Сначала пройди /start.")
            return
        meals = await crud.get_meals_for_day(session, message.from_user.id)

    if not meals:
        await message.answer("За сегодня приемов пищи пока нет.")
        return

    for meal in meals:
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Удалить", callback_data=f"meal_delete:{meal.id}")]
            ]
        )
        await message.answer(
            f"#{meal.id} {meal.description}\n"
            f"{meal.calories:.1f} ккал | Б {meal.protein_g:.1f} | Ж {meal.fat_g:.1f} | У {meal.carbs_g:.1f}",
            reply_markup=kb,
        )


@router.callback_query(lambda c: c.data and c.data.startswith("meal_delete:"))
async def meal_delete(callback) -> None:  # type: ignore[no-untyped-def]
    if not callback.from_user:
        await callback.answer()
        return
    meal_id = int(callback.data.split(":")[1])
    ctx = get_app_context()
    async with ctx.sessionmaker() as session:
        ok = await crud.delete_meal_log(session, callback.from_user.id, meal_id)
    await callback.answer("Удалено" if ok else "Не найдено")
    if callback.message:
        await callback.message.edit_text("Удалено.")


@router.message(F.photo)
async def photo_meal(message: Message) -> None:
    if not message.from_user or not message.photo:
        return
    ctx = get_app_context()
    async with ctx.sessionmaker() as session:
        user = await crud.get_user(session, message.from_user.id)
        if user is None:
            await message.answer("Сначала пройди /start.")
            return

    photo = message.photo[-1]
    file = await message.bot.get_file(photo.file_id)
    image_url = f"https://api.telegram.org/file/bot{ctx.settings.telegram_bot_token}/{file.file_path}"
    caption = (message.caption or "").strip() or None

    try:
        parsed = await analyze_meal_photo(
            ctx.agent.client,
            ctx.settings.openai_model_vision,
            image_url,
            caption=caption,
        )
    except Exception:  # noqa: BLE001
        await message.answer("Не удалось распознать фото. Попробуй еще раз или опиши блюдо текстом.")
        return

    async with ctx.sessionmaker() as session:
        await crud.add_meal_log(
            session=session,
            telegram_id=message.from_user.id,
            description=str(parsed["description"]),
            calories=float(parsed["calories"]),
            protein_g=float(parsed["protein_g"]),
            fat_g=float(parsed["fat_g"]),
            carbs_g=float(parsed["carbs_g"]),
            photo_file_id=photo.file_id,
            meal_type="snack",
        )
        user = await crud.get_user(session, message.from_user.id)
        consumed = await crud.get_meal_summary_for_day(session, message.from_user.id)

    if user is None:
        await message.answer("Сначала пройди /start.")
        return
    await message.answer(
        "Записал прием пищи по фото:\n"
        f"{parsed['description']}\n"
        f"{float(parsed['calories']):.1f} ккал | Б {float(parsed['protein_g']):.1f} | "
        f"Ж {float(parsed['fat_g']):.1f} | У {float(parsed['carbs_g']):.1f}\n\n"
        f"{progress_text(consumed, user)}"
    )


@router.message(
    F.text & ~F.text.startswith("/") & ~F.text.in_(MAIN_MENU_BUTTONS),
    ~StateFilter(WeightStates),
    ~StateFilter(OnboardingStates),
)
async def text_message(message: Message) -> None:
    if not message.from_user or not message.text:
        return
    ctx = get_app_context()
    async with ctx.sessionmaker() as session:
        user = await crud.get_user(session, message.from_user.id)
    if user is None:
        await message.answer("Сначала пройди /start.")
        return

    context = (
        f"telegram_id={message.from_user.id}. "
        "Пользователь может описывать приём пищи или задавать вопросы по питанию. "
        "При вызове add_meal всегда передавай telegram_id из контекста."
    )
    user_id = message.from_user.id
    history = CONVERSATION_HISTORY.get(user_id, [])[-MAX_HISTORY_PAIRS:]
    try:
        answer = await ctx.agent.ask(
            message.text,
            context=context,
            history=history if history else None,
        )
    except Exception:  # noqa: BLE001
        await message.answer("Сервис ИИ временно недоступен. Попробуй позже.")
        return
    # Добавляем пару в историю и обрезаем до MAX_HISTORY_PAIRS
    if user_id not in CONVERSATION_HISTORY:
        CONVERSATION_HISTORY[user_id] = []
    CONVERSATION_HISTORY[user_id].append((message.text.strip(), answer))
    CONVERSATION_HISTORY[user_id] = CONVERSATION_HISTORY[user_id][-MAX_HISTORY_PAIRS:]
    await message.answer(answer)

