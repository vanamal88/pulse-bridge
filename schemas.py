from datetime import datetime
from typing import Any
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.models.message import MediaType
class ChatRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    peer_tg_id: int
    peer_name: str | None
    created_at: datetime
class MessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    chat_id: UUID
    tg_message_id: int
    direction: str
    text: str
    media_type: MediaType | None
    file_id: str | None
    file_unique_id: str | None
    file_meta: dict[str, Any] | None
    sent_at: datetime
    edited_at: datetime | None
class MessageCreate(BaseModel):
    chat_id: UUID
    client_message_id: str = Field(min_length=8, max_length=128)
    text: str = Field(default="", max_length=4096)
    media_type: MediaType | None = None
    file_id: str | None = None
    @model_validator(mode="after")
    def validate_content(self):
        if not self.text and not self.media_type: raise ValueError("Message text or media is required")
        if self.media_type and not self.file_id: raise ValueError("file_id is required for media")
        return self
class WsTokenResponse(BaseModel):
    token: str
    expires_in: int
