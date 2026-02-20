from __future__ import annotations

import logging
from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, or_f, StateFilter
from aiogram.types import BufferedInputFile, InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot.database import crud
from bot.handlers.start import OnboardingStates
from bot.handlers.weight import WeightStates
from bot.keyboards import BTN_HISTORY, MAIN_MENU_BUTTONS
from bot.prompts import context_message
from bot.runtime import get_app_context
from bot.services.pending_media import pop_pending_photos

logger = logging.getLogger(__name__)

MAX_HISTORY_PAIRS = 10

router = Router()


@router.message(or_f(Command("history"), F.text == BTN_HISTORY))
async def history(message: Message) -> None:
    if not message.from_user:
        return
    ctx = get_app_context()
    tz = ZoneInfo(ctx.settings.league_report_timezone)
    async with ctx.sessionmaker() as session:
        user = await crud.get_user(session, message.from_user.id)
        if user is None:
            await message.answer("Сначала пройди /start.")
            return
        meals = await crud.get_meals_for_day(session, message.from_user.id, timezone=tz)

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
    file = await message.bot.get_file(photo.file_id)  # type: ignore[union-attr]
    image_url = f"https://api.telegram.org/file/bot{ctx.settings.telegram_bot_token}/{file.file_path}"
    caption = (message.caption or "").strip() or "Пользователь отправил фото еды. Оцени КБЖУ и запиши приём пищи."

    context = context_message(
        message.from_user.id,
        timezone_name=ctx.settings.league_report_timezone,
        chat_id=message.chat.id if message.chat else None,
    )
    user_id = message.from_user.id
    async with ctx.sessionmaker() as session:
        history = await crud.get_recent_conversation(session, user_id, limit=MAX_HISTORY_PAIRS)
    try:
        answer = await ctx.agent.ask(
            caption,
            context=context,
            history=history if history else None,
            image_urls=[image_url],
        )
    except Exception:  # noqa: BLE001
        logger.exception("Agent failed on photo message")
        await message.answer("Не удалось распознать фото. Попробуй ещё раз или опиши блюдо текстом.")
        return

    async with ctx.sessionmaker() as session:
        await crud.add_conversation_message(session, user_id, "user", f"[фото еды] {caption}")
        await crud.add_conversation_message(session, user_id, "assistant", answer)
        await crud.clear_old_conversation(session, user_id, keep_pairs=MAX_HISTORY_PAIRS)
    try:
        await message.answer(answer, parse_mode="HTML")
    except TelegramBadRequest:
        await message.answer(answer)
    pending = pop_pending_photos(user_id)
    for item in pending:
        await message.answer_photo(
            photo=BufferedInputFile(item.content, filename=item.filename),
            caption=item.caption,
            reply_markup=item.keyboard,
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
    is_group_chat = message.chat.type in {"group", "supergroup"}
    league_request = "лига" in message.text.lower()
    async with ctx.sessionmaker() as session:
        user = await crud.get_user(session, message.from_user.id)
    if user is None and not is_group_chat:
        await message.answer("Сначала пройди /start.")
        return
    if user is None and is_group_chat and not league_request:
        await message.answer("Для личного учёта открой бота в личке и пройди /start.")
        return

    context = context_message(
        message.from_user.id,
        timezone_name=ctx.settings.league_report_timezone,
        chat_id=message.chat.id if message.chat else None,
    )
    user_id = message.from_user.id
    async with ctx.sessionmaker() as session:
        history = await crud.get_recent_conversation(session, user_id, limit=MAX_HISTORY_PAIRS)
    try:
        answer = await ctx.agent.ask(
            message.text,
            context=context,
            history=history if history else None,
        )
    except Exception:  # noqa: BLE001
        logger.exception("Agent failed on text message")
        await message.answer("Сервис ИИ временно недоступен. Попробуй позже.")
        return
    async with ctx.sessionmaker() as session:
        await crud.add_conversation_message(session, user_id, "user", message.text.strip())
        await crud.add_conversation_message(session, user_id, "assistant", answer)
        await crud.clear_old_conversation(session, user_id, keep_pairs=MAX_HISTORY_PAIRS)
    try:
        await message.answer(answer, parse_mode="HTML")
    except TelegramBadRequest:
        await message.answer(answer)
    pending = pop_pending_photos(user_id)
    for item in pending:
        await message.answer_photo(
            photo=BufferedInputFile(item.content, filename=item.filename),
            caption=item.caption,
            reply_markup=item.keyboard,
        )

