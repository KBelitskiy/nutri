from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandStart, or_f
from aiogram.types import ChatMemberUpdated, Message

from bot.database import crud
from bot.keyboards import BTN_LEAGUE_TODAY, BTN_LEAGUE_WEEK, GROUP_MENU_KB
from bot.runtime import get_app_context
from bot.services.league_reports import build_daily_league_report, build_weekly_league_report

router = Router()

_ACTIVE_STATUSES = {"member", "administrator", "creator", "restricted"}


def _is_group(chat_type: str) -> bool:
    return chat_type in {"group", "supergroup"}


@router.my_chat_member()
async def bot_chat_member_update(event: ChatMemberUpdated) -> None:
    if not _is_group(event.chat.type):
        return

    old_status = event.old_chat_member.status
    new_status = event.new_chat_member.status
    chat_id = event.chat.id
    title = event.chat.title

    ctx = get_app_context()
    async with ctx.sessionmaker() as session:
        if new_status in _ACTIVE_STATUSES:
            await crud.add_group_chat(session, chat_id, title=title)
        elif old_status in _ACTIVE_STATUSES and new_status in {"left", "kicked"}:
            await crud.remove_group_chat(session, chat_id)


@router.message(
    or_f(Command("league_today"), F.text == BTN_LEAGUE_TODAY),
    F.chat.type.in_({"group", "supergroup"}),
)
async def send_manual_daily_league_report(message: Message) -> None:
    if not message.from_user:
        return
    ctx = get_app_context()
    async with ctx.sessionmaker() as session:
        await crud.add_group_chat(session, message.chat.id, title=message.chat.title)
        await crud.ensure_group_member(session, message.chat.id, message.from_user.id)
        report = await build_daily_league_report(
            session, message.chat.id, ctx.settings.league_report_timezone
        )
    await message.answer(report or "Сегодня нет данных для сводки.")


@router.message(
    or_f(Command("league_week"), F.text == BTN_LEAGUE_WEEK),
    F.chat.type.in_({"group", "supergroup"}),
)
async def send_manual_weekly_league_report(message: Message) -> None:
    if not message.from_user:
        return
    ctx = get_app_context()
    async with ctx.sessionmaker() as session:
        await crud.add_group_chat(session, message.chat.id, title=message.chat.title)
        await crud.ensure_group_member(session, message.chat.id, message.from_user.id)
        report = await build_weekly_league_report(
            session, message.chat.id, ctx.settings.league_report_timezone
        )
    await message.answer(report or "За неделю нет данных для сводки.")


@router.message(CommandStart(), F.chat.type.in_({"group", "supergroup"}))
async def group_start(message: Message) -> None:
    await message.answer(
        "Привет! В группе доступны лиговые сводки: /league_today и /league_week.\n"
        "Для личного профиля и учета питания открой диалог с ботом в личке и нажми /start.",
        reply_markup=GROUP_MENU_KB,
    )


@router.message(F.chat.type.in_({"group", "supergroup"}), F.text & ~F.text.startswith("/"))
async def register_group_message_author(message: Message) -> None:
    if not message.from_user:
        return

    ctx = get_app_context()
    async with ctx.sessionmaker() as session:
        await crud.add_group_chat(session, message.chat.id, title=message.chat.title)
        await crud.ensure_group_member(session, message.chat.id, message.from_user.id)
