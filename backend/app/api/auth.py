"""Auth API routes."""

from __future__ import annotations

import re
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.core.audit import log_login_attempt, log_token_blacklist
from app.core.dependencies import (
    blacklist_token,
    check_brute_force,
    get_current_user,
    record_failed_attempt,
    reset_brute_force,
)
from app.core.logging import get_logger
from app.core.rate_limiter import check_auth_rate_limit
from app.core.security import sanitize_filename
from app.database import get_db
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

# Password strength validation
_PASSWORD_UPPERCASE = re.compile(r"[A-Z]")
_PASSWORD_LOWERCASE = re.compile(r"[a-z]")
_PASSWORD_DIGIT = re.compile(r"\d")


def _validate_password_strength(password: str) -> None:
    """Validate password meets strength requirements."""
    if len(password) < 8:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Password must be at least 8 characters long",
        )
    if len(password) > 128:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Password must not exceed 128 characters",
        )
    if not _PASSWORD_UPPERCASE.search(password):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Password must contain at least one uppercase letter",
        )
    if not _PASSWORD_LOWERCASE.search(password):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Password must contain at least one lowercase letter",
        )
    if not _PASSWORD_DIGIT.search(password):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Password must contain at least one digit",
        )


def _get_client_ip(request: Request) -> str:
    """Extract client IP from request."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Register a new user account."""
    # Rate limit auth requests
    await check_auth_rate_limit(request)

    client_ip = _get_client_ip(request)

    # Validate password strength
    _validate_password_strength(body.password)

    # Sanitize display name
    display_name = sanitize_filename(body.display_name) or body.display_name

    # Check if email already exists
    result = await db.execute(select(User).where(User.email == body.email))
    if result.scalar_one_or_none() is not None:
        await log_login_attempt(body.email, client_ip, success=False, reason="email_exists")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    user = User(
        email=body.email,
        password_hash=hash_password(body.password),
        display_name=display_name,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)

    access_token = create_access_token(str(user.id))
    refresh_token = create_refresh_token(str(user.id))

    await log_login_attempt(body.email, client_ip, success=True)

    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Authenticate a user and return tokens."""
    # Rate limit auth requests
    await check_auth_rate_limit(request)

    client_ip = _get_client_ip(request)
    brute_force_key = f"{body.email}:{client_ip}"

    # Check brute force lockout
    if not await check_brute_force(
        brute_force_key,
        max_attempts=5,
        lockout_minutes=15,
    ):
        await log_login_attempt(
            body.email, client_ip, success=False, reason="account_locked"
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Please try again in 15 minutes.",
        )

    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if user is None or not verify_password(body.password, user.password_hash):
        await record_failed_attempt(brute_force_key)
        await log_login_attempt(body.email, client_ip, success=False, reason="invalid_credentials")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if user.deleted_at is not None:
        await log_login_attempt(body.email, client_ip, success=False, reason="deactivated")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account has been deactivated",
        )

    # Reset brute force counter on successful login
    await reset_brute_force(brute_force_key)

    access_token = create_access_token(str(user.id))
    refresh_token = create_refresh_token(str(user.id))

    await log_login_attempt(body.email, client_ip, success=True)

    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    body: RefreshRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Refresh an access token using a refresh token."""
    # Rate limit auth requests
    await check_auth_rate_limit(request)

    try:
        payload = decode_token(body.refresh_token)
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type — use a refresh token",
            )
        user_id_str = payload.get("sub")
        if user_id_str is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
            )
        user_id = uuid.UUID(user_id_str)
    except (JWTError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None or user.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or deactivated",
        )

    access_token = create_access_token(str(user.id))
    new_refresh_token = create_refresh_token(str(user.id))

    return TokenResponse(access_token=access_token, refresh_token=new_refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def logout(
    body: LogoutRequest | None = None,
    current_user: User = Depends(get_current_user),
) -> Response:
    """Logout by blacklisting the current token."""
    if body and body.access_token:
        try:
            payload = decode_token(body.access_token)

            # Use the token's JTI for blacklisting
            jti = payload.get("jti", f"{payload.get('sub', '')}:{payload.get('iat', 0)}")
            await log_token_blacklist(jti, str(current_user.id), reason="logout")
            # Blacklist the token
            await blacklist_token(jti)
            logger.info(
                "User logged out",
                user_id=str(current_user.id),
                token_blacklisted=True,
            )
        except Exception:
            logger.warning(
                "Failed to blacklist token on logout",
                user_id=str(current_user.id),
            )

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)) -> UserResponse:
    """Get the current user's profile."""
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        display_name=current_user.display_name,
        created_at=current_user.created_at.isoformat(),
    )