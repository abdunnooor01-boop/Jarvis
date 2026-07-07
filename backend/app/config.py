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

    # Security — Auth Hardening
    brute_force_max_attempts: int = 5
    brute_force_lockout_minutes: int = 15
    password_min_length: int = 8
    password_require_uppercase: bool = True
    password_require_lowercase: bool = True
    password_require_digit: bool = True

    # Security — WebSocket
    ws_max_message_size: int = 65_536  # 64 KB
    ws_max_messages_per_minute: int = 50
    ws_max_connections_per_user: int = 5

    # Security — Request Validation
    max_request_body_size: int = 10 * 1024 * 1024  # 10 MB
    max_prompt_length: int = 32_000

    # LLM
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o"
    anthropic_api_key: str | None = None
    gemini_api_key: str | None = None

    # Tools
    tavily_api_key: str | None = None

    # Stripe
    stripe_secret_key: str | None = None
    stripe_webhook_secret: str | None = None

    # CORS
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    # Rate Limiting
    rate_limit_chat: int = 100  # requests per minute
    rate_limit_api: int = 1000  # requests per minute

    # Paths
    tools_dir: str = str(Path(__file__).parent / "tools")
    plugins_dir: str = str(Path(__file__).parent / "plugins")


settings = Settings()