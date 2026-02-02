from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict
class Settings(BaseSettings):
    """환경설정 로더.

    Attributes:
        POSTGRES_CONNECTION_STRING: SQLAlchemy async DB URL.
        TOKEN_TTL_MINUTES: 토큰 만료(분).
    """
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    POSTGRES_CONNECTION_STRING: str: str
    TOKEN_TTL_MINUTES: int = 60 * 24


settings: Settings = Settings()
