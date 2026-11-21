import uuid
from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint, func, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base

class TelegramConnection(Base):
    __tablename__ = "telegram_connections"
    __table_args__ = (UniqueConstraint("business_connection_id", name="uq_business_connection_id"),)
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    business_connection_id: Mapped[str] = mapped_column(String(256), index=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    can_reply: Mapped[bool] = mapped_column(Boolean, default=False)
    connected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    user = relationship("User", back_populates="connections")
