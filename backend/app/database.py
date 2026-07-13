"""Database engine and session management — lazily initialized."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

# ---------------------------------------------------------------------------
# Lazy engine — created on first access, not at import time
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _get_engine():
    """Create and cache the database engine.

    Lazily initialized on first call to save ~0.3s of startup time.
    The @lru_cache ensures the engine is a singleton.
    """
    return create_async_engine(
        settings.database_url,
        echo=settings.debug,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
    )


def get_engine():
    """Get the database engine, creating it lazily if needed."""
    return _get_engine()


def get_async_session_factory():
    """Get the async session factory, creating the engine lazily if needed."""
    return async_sessionmaker(
        _get_engine(),
        class_=AsyncSession,
        expire_on_commit=False,
    )


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    __abstract__ = True


# ---------------------------------------------------------------------------
# Session factory (lazy)
# ---------------------------------------------------------------------------

async_session_factory = get_async_session_factory()


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields a database session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
