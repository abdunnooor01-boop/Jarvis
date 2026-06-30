"""Application configuration via pydantic-settings."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    app_name: str = "Jarvis API"
    app_version: str = "0.1.0"
    debug: bool = False
    environment: Literal["development", "staging", "production"] = "development"

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # Database
    database_url: str = "postgresql+asyncpg://jarvis:jarvis@localhost:5432/jarvis"
    database_url_sync: str = "postgresql://jarvis:jarvis@localhost:5432/jarvis"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Auth
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 7

    # LLM
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o"
    anthropic_api_key: str | None = None
    gemini_api_key: str | None = None

    # Tools
    tavily_api_key: str | None = None

    # CORS
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    # Rate Limiting
    rate_limit_chat: int = 100  # requests per minute
    rate_limit_api: int = 1000  # requests per minute

    # Paths
    tools_dir: str = str(Path(__file__).parent / "tools")
    plugins_dir: str = str(Path(__file__).parent / "plugins")


settings = Settings()
