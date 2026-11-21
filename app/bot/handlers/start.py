from datetime import datetime, timezone
from aiogram import Router
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from sqlalchemy import select
from app.database import get_session_factory
from app.models import TelegramConnection, User
from app.services.users import get_or_create_user, issue_key_if_missing, rotate_key
router = Router(name="start")

@router.message(CommandStart())
async def start(message: Message):
    async with get_session_factory()() as db:
        user = await get_or_create_user(db, message.from_user.id, message.from_user.first_name, message.from_user.username)
        key = await issue_key_if_missing(db, user)
        conn = await db.scalar(select(TelegramConnection).where(TelegramConnection.user_id == user.id, TelegramConnection.is_enabled.is_(True)))
        await db.commit()
    text = "<b>PULSE Bridge</b>\n\nБот связывает Telegram Business с приложением PULSE. Он не отвечает собеседникам самостоятельно."
    if key:
        text += "\n\n<b>Твой API-ключ (показывается только сейчас):</b>\n<code>" + key + "</code>\n\nСохрани его в настройках PULSE. Не отправляй никому."
    else:
        text += "\n\nAPI-ключ уже создан. Если потерял его, используй /newkey для перевыпуска. Старый ключ перестанет работать."
    text += "\n\nСтатус Telegram Business: " + ("подключён" if conn else "не подключён")
    text += "\nПодключение: Telegram → Настройки → Telegram Business → Чат-боты → добавить @PulseBridge_Bot."
    await message.answer(text)

@router.message(Command("newkey"))
async def new_key(message: Message):
    async with get_session_factory()() as db:
        user = await get_or_create_user(db, message.from_user.id, message.from_user.first_name, message.from_user.username)
        key = await rotate_key(db, user)
        await db.commit()
    await message.answer("<b>Новый API-ключ:</b>\n<code>" + key + "</code>\n\nСохрани его. Предыдущие ключи отозваны.")

@router.message(Command("status"))
async def status(message: Message):
    async with get_session_factory()() as db:
        user = await db.scalar(select(User).where(User.tg_user_id == message.from_user.id))
        conn = await db.scalar(select(TelegramConnection).where(TelegramConnection.user_id == user.id, TelegramConnection.is_enabled.is_(True))) if user else None
    await message.answer("PULSE Bridge: работает\nTelegram Business: " + ("подключён" if conn else "не подключён") + ("\nПраво отвечать: " + ("есть" if conn.can_reply else "нет") if conn else ""))
