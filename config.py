from functools import lru_cache
from typing import Literal
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False)
    BOT_TOKEN: str = Field(min_length=20)
    WEBHOOK_SECRET: str = Field(min_length=32)
    DATABASE_URL: str
    BOT_MODE: Literal["webhook", "polling"] = "webhook"
    WEBHOOK_BASE_URL: str | None = None
    LOG_LEVEL: str = "INFO"
    WS_TOKEN_TTL: int = Field(default=60, ge=15, le=300)
    MAX_FILE_BYTES: int = Field(default=20 * 1024 * 1024, ge=1024, le=50 * 1024 * 1024)
    @field_validator("DATABASE_URL")
    @classmethod
    def normalize_db_url(cls, value: str) -> str:
        if value.startswith("postgres://"):
            return value.replace("postgres://", "postgresql+asyncpg://", 1)
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+asyncpg://", 1)
        return value
    @field_validator("WEBHOOK_BASE_URL")
    @classmethod
    def clean_url(cls, value):
        return value.rstrip("/") if value else value
    @property
    def webhook_path(self) -> str:
        return f"/telegram/webhook/{self.WEBHOOK_SECRET[:24]}"
    @property
    def full_webhook_url(self) -> str:
        if not self.WEBHOOK_BASE_URL:
            raise RuntimeError("WEBHOOK_BASE_URL is required in webhook mode")
        return self.WEBHOOK_BASE_URL + self.webhook_path

@lru_cache
def get_settings() -> Settings:
    return Settings()
