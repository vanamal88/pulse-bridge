from dataclasses import dataclass
from typing import Any
from aiogram import Bot
from aiogram.types import Message
from app.models.message import MediaType

@dataclass
class SendResult:
    message_id: int
    file_id: str | None = None
    file_unique_id: str | None = None
    file_meta: dict[str, Any] | None = None

class TelegramService:
    def __init__(self, bot: Bot): self.bot = bot
    async def send_business_message(self, bcid: str, chat_id: int, text: str, media_type: MediaType | None, file_id: str | None) -> SendResult:
        common = {"chat_id": chat_id, "business_connection_id": bcid}
        if media_type is None:
            msg = await self.bot.send_message(**common, text=text)
        elif media_type == MediaType.photo:
            msg = await self.bot.send_photo(**common, photo=file_id, caption=text or None)
        elif media_type == MediaType.video:
            msg = await self.bot.send_video(**common, video=file_id, caption=text or None)
        elif media_type == MediaType.document:
            msg = await self.bot.send_document(**common, document=file_id, caption=text or None)
        elif media_type == MediaType.voice:
            msg = await self.bot.send_voice(**common, voice=file_id, caption=text or None)
        elif media_type == MediaType.audio:
            msg = await self.bot.send_audio(**common, audio=file_id, caption=text or None)
        elif media_type == MediaType.video_note:
            msg = await self.bot.send_video_note(**common, video_note=file_id)
        else: raise ValueError("Unsupported media type")
        media_obj = getattr(msg, media_type.value, None) if media_type else None
        if media_type == MediaType.photo and msg.photo: media_obj = msg.photo[-1]
        meta = None
        if media_obj:
            meta = {k: getattr(media_obj, k, None) for k in ("width", "height", "duration", "file_size", "mime_type", "file_name", "length") if getattr(media_obj, k, None) is not None}
        return SendResult(msg.message_id, getattr(media_obj, "file_id", None), getattr(media_obj, "file_unique_id", None), meta)
