"""Auth-related Pydantic schemas."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    """Registration request payload."""

    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    display_name: str = Field(..., min_length=1, max_length=100)


class LoginRequest(BaseModel):
    """Login request payload."""

    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """JWT token response."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    """Refresh token request payload."""

    refresh_token: str


class LogoutRequest(BaseModel):
    """Logout request payload (optional — token can be inferred from auth header)."""

    access_token: str | None = None


class UserResponse(BaseModel):
    """Public user profile response."""

    id: UUID
    email: str
    display_name: str
    created_at: str


class ErrorResponse(BaseModel):
    """RFC 7807 Problem Details error response."""

    type: str = "about:blank"
    title: str
    status: int
    detail: str
    instance: str | None = None