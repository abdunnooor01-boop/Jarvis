"""Auth API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
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
from app.core.dependencies import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    """Register a new user account."""
    # Check if email already exists
    result = await db.execute(select(User).where(User.email == body.email))
    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    user = User(
        email=body.email,
        password_hash=hash_password(body.password),
        display_name=body.display_name,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)

    access_token = create_access_token(str(user.id))
    refresh_token = create_refresh_token(str(user.id))

    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    """Authenticate a user and return tokens."""
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if user.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account has been deactivated",
        )

    access_token = create_access_token(str(user.id))
    refresh_token = create_refresh_token(str(user.id))

    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    """Refresh an access token using a refresh token."""
    try:
        payload = decode_token(body.refresh_token)
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type — use a refresh token",
            )
        user_id = payload.get("sub")
    except JWTError:
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


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)) -> UserResponse:
    """Get the current user's profile."""
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        display_name=current_user.display_name,
        created_at=current_user.created_at.isoformat(),
    )