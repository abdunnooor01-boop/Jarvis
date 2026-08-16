"""Authentication utilities: JWT, password hashing."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from jose import jwt
from passlib.context import CryptContext

from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a plain-text password using bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain-text password against a bcrypt hash."""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(subject: str) -> str:
    """Create a short-lived JWT access token."""
    now = datetime.now(UTC)
    expires = now + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    payload = {
        "sub": subject,
        "exp": expires,
        "iat": now,
        "type": "access",
    }
    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def create_refresh_token(subject: str) -> str:
    """Create a long-lived JWT refresh token."""
    now = datetime.now(UTC)
    expires = now + timedelta(days=settings.jwt_refresh_token_expire_days)
    payload = {
        "sub": subject,
        "exp": expires,
        "iat": now,
        "type": "refresh",
    }
    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def decode_token(token: str) -> dict:
    """Decode and validate a JWT token. Raises JWTError on failure."""
    return jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
    )
