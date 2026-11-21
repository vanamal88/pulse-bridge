import uuid
from datetime import datetime
from sqlalchemy import BigInteger, DateTime, ForeignKey, String, UniqueConstraint, func, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base

class Chat(Base):
    __tablename__ = "chats"
    __table_args__ = (UniqueConstraint("connection_id", "peer_tg_id", name="uq_chat_connection_peer"),)
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    connection_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("telegram_connections.id", ondelete="CASCADE"), index=True)
    peer_tg_id: Mapped[int] = mapped_column(BigInteger)
    peer_name: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    user = relationship("User", back_populates="chats")
    messages = relationship("Message", back_populates="chat", cascade="all, delete-orphan")
