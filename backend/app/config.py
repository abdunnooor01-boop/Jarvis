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
    app_base_url: str = "http://localhost:3000"
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
    llm_provider: str = "openai"  # openai, ollama
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3"

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

    # Performance & Power
    low_power_mode: bool = False
    max_memory_mb: int = 0  # 0 = unlimited
    max_concurrent_tasks: int = 5
    crawl_interval_hours: int = 24  # How often to crawl (default: daily)
    digest_day_of_week: int = 6  # 0=Mon, 6=Sun — day to generate weekly digest


settings = Settings()
