"""Standalone test configuration for testing engine tests.

This conftest does NOT import app.main (which has a pre-existing bug
with duplicate FreelanceJob models). Instead, it sets up the database
and testing engine directly.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

import pytest
import pytest_asyncio
from pathlib import Path
import tempfile

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.database import Base
from app.models.testing import TestResult, TestRun  # noqa: F401 - ensures tables are registered

# pytest-asyncio runs each async test on its own event loop, so an in-memory
# SQLite StaticPool connection would be bound to one loop and cannot be reused
# on the next loop (MissingGreenlet). Use a temporary file DB with NullPool so
# each connection is fresh on the current loop while the on-disk data is
# shared by every session. A single temp dir is created per run.
_TEST_TMPDIR = tempfile.mkdtemp(prefix="jarvis-testing-db")
_TEST_DB_FILE = Path(_TEST_TMPDIR) / "testing.db"
TEST_DATABASE_URL = f"sqlite+aiosqlite:///{_TEST_DB_FILE}"

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False, poolclass=NullPool)
test_session_factory = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest_asyncio.fixture(autouse=True)
async def setup_database() -> AsyncGenerator[None, None]:
    """Create tables before each test and drop after."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Get a test database session directly."""
    async with test_session_factory() as session:
        yield session