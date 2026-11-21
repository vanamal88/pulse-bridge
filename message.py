import enum, uuid
from datetime import datetime
from typing import Any
from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, String, Text, UniqueConstraint, func, Uuid, JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base

class Direction(str, enum.Enum):
    inbound = "inbound"
    outbound = "outbound"
class MediaType(str, enum.Enum):
    photo = "photo"
    video = "video"
    document = "document"
    voice = "voice"
    audio = "audio"
    video_note = "video_note"
class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (UniqueConstraint("chat_id", "tg_message_id", name="uq_message_chat_tg_id"),)
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    chat_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("chats.id", ondelete="CASCADE"), index=True)
    tg_message_id: Mapped[int] = mapped_column(BigInteger)
    direction: Mapped[Direction] = mapped_column(Enum(Direction, name="message_direction"))
    text: Mapped[str] = mapped_column(Text, default="")
    media_type: Mapped[MediaType | None] = mapped_column(Enum(MediaType, name="media_type"), nullable=True)
    file_id: Mapped[str | None] = mapped_column(String(512))
    file_unique_id: Mapped[str | None] = mapped_column(String(128))
    file_meta: Mapped[dict[str, Any] | None] = mapped_column(JSON().with_variant(JSONB(), "postgresql"))
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    chat = relationship("Chat", back_populates="messages")
