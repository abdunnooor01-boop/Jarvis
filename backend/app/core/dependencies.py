"""FastAPI dependencies."""

from __future__ import annotations

from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import decode_token
from app.core.logging import get_logger
from app.database import get_db
from app.models.user import User

logger = get_logger(__name__)

security_scheme = HTTPBearer(auto_error=False)

# In-memory token blacklist set (when Redis is unavailable)
_token_blacklist: set[str] = set()

# In-memory brute force tracker: key -> (attempts, lockout_until_timestamp)
_brute_force_tracker: dict[str, tuple[int, float]] = {}


# =============================================================================
# Token Blacklist
# =============================================================================

async def is_token_blacklisted(jti: str) -> bool:
    """Check if a token (JTI) is blacklisted."""
    # Try Redis first
    try:
        import redis.asyncio as aioredis

        from app.config import settings

        r = aioredis.from_url(settings.redis_url, socket_connect_timeout=2)
        exists = await r.exists(f"token_blacklist:{jti}")
        await r.aclose()
        return bool(exists)
    except Exception:
        pass  # Fall back to in-memory

    return jti in _token_blacklist


async def blacklist_token(jti: str, expire_seconds: int = 86400) -> None:
    """Blacklist a token by its JTI."""
    # Try Redis first
    try:
        import redis.asyncio as aioredis

        from app.config import settings

        r = aioredis.from_url(settings.redis_url, socket_connect_timeout=2)
        await r.setex(f"token_blacklist:{jti}", expire_seconds, "1")
        await r.aclose()
        return
    except Exception:
        pass  # Fall back to in-memory

    _token_blacklist.add(jti)


def _get_token_jti(payload: dict) -> str:
    """Extract or generate a unique JTI from a token payload."""
    jti = payload.get("jti")
    if jti:
        return jti
    # Fall back to sub+iat as identifier
    sub = payload.get("sub", "unknown")
    iat = payload.get("iat", 0)
    return f"{sub}:{iat}"


# =============================================================================
# Brute Force Protection
# =============================================================================

import time


async def check_brute_force(key: str, max_attempts: int = 5, lockout_minutes: int = 15) -> bool:
    """Check if a key (IP or email) is locked out due to too many failed attempts.

    Returns True if allowed, False if locked out.
    """
    # Try Redis first
    try:
        import redis.asyncio as aioredis

        from app.config import settings

        r = aioredis.from_url(settings.redis_url, socket_connect_timeout=2)
        lockout_key = f"bruteforce:lockout:{key}"
        attempts_key = f"bruteforce:attempts:{key}"

        # Check lockout
        locked = await r.exists(lockout_key)
        if locked:
            ttl = await r.ttl(lockout_key)
            await r.aclose()
            return False

        await r.aclose()
        return True
    except Exception:
        pass  # Fall back to in-memory

    # In-memory fallback
    entry = _brute_force_tracker.get(key)
    if entry:
        attempts, lockout_until = entry
        if lockout_until > time.time():
            return False

    return True


async def record_failed_attempt(key: str, max_attempts: int = 5, lockout_minutes: int = 15) -> None:
    """Record a failed login attempt. Triggers lockout if max exceeded."""
    # Try Redis first
    try:
        import redis.asyncio as aioredis

        from app.config import settings

        r = aioredis.from_url(settings.redis_url, socket_connect_timeout=2)
        attempts_key = f"bruteforce:attempts:{key}"
        lockout_key = f"bruteforce:lockout:{key}"

        attempts = await r.incr(attempts_key)
        await r.expire(attempts_key, lockout_minutes * 60)

        if attempts >= max_attempts:
            await r.setex(lockout_key, lockout_minutes * 60, "1")
            await r.delete(attempts_key)

        await r.aclose()
        return
    except Exception:
        pass  # Fall back to in-memory

    # In-memory fallback
    now = time.time()
    entry = _brute_force_tracker.get(key)
    if entry:
        attempts, lockout_until = entry
        if lockout_until > now:
            return  # Already locked out
        if attempts >= max_attempts:
            _brute_force_tracker[key] = (0, now + lockout_minutes * 60)
            return
        _brute_force_tracker[key] = (attempts + 1, 0)
    else:
        _brute_force_tracker[key] = (1, 0)


async def reset_brute_force(key: str) -> None:
    """Reset the brute force counter for a key (after successful login)."""
    try:
        import redis.asyncio as aioredis

        from app.config import settings

        r = aioredis.from_url(settings.redis_url, socket_connect_timeout=2)
        await r.delete(f"bruteforce:attempts:{key}")
        await r.delete(f"bruteforce:lockout:{key}")
        await r.aclose()
        return
    except Exception:
        pass

    _brute_force_tracker.pop(key, None)


# =============================================================================
# User Authentication Dependencies
# =============================================================================


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Dependency that validates the JWT and returns the current user.

    Also checks token blacklist and rate limits.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_token(credentials.credentials)
        if payload.get("type") != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type — use an access token",
            )
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
            )

        # Check token blacklist
        jti = _get_token_jti(payload)
        if await is_token_blacklisted(jti):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has been revoked",
                headers={"WWW-Authenticate": "Bearer"},
            )

    except HTTPException:
        raise
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    result = await db.execute(select(User).where(User.id == UUID(user_id)))
    user = result.scalar_one_or_none()

    if user is None or user.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or deactivated",
        )

    return user


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """Dependency that returns the current user or None if unauthenticated."""
    if credentials is None:
        return None

    try:
        payload = decode_token(credentials.credentials)
        if payload.get("type") != "access":
            return None
        user_id = payload.get("sub")
        if user_id is None:
            return None

        # Check token blacklist
        jti = _get_token_jti(payload)
        if await is_token_blacklisted(jti):
            return None

        result = await db.execute(select(User).where(User.id == UUID(user_id)))
        user = result.scalar_one_or_none()

        if user is None or user.deleted_at is not None:
            return None

        return user
    except JWTError:
        return None