"""System endpoints — connectivity checks, health, and status."""

from __future__ import annotations

import asyncio
import socket
from typing import Any

import httpx
from fastapi import APIRouter

from app.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/system", tags=["system"])


async def _check_internet() -> bool:
    """Check if the machine has general internet connectivity."""
    try:
        # Try to reach a reliable endpoint
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get("https://1.1.1.1")
            return resp.status_code < 500
    except Exception:
        # Fallback: try DNS resolution
        try:
            socket.getaddrinfo("google.com", 80)
            return True
        except Exception:
            return False


async def _check_openai() -> bool:
    """Check if the OpenAI API is reachable."""
    if not settings.openai_api_key:
        return False
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                "https://api.openai.com/v1/models",
                headers={"Authorization": f"Bearer {settings.openai_api_key}"},
            )
            return resp.status_code < 500
    except Exception:
        return False


async def _check_ollama() -> bool:
    """Check if Ollama is reachable (local by default)."""
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get("http://localhost:11434/api/tags")
            return resp.status_code < 500
    except Exception:
        return False


@router.get("/connectivity")
async def check_connectivity() -> dict[str, Any]:
    """Check connectivity to external services.

    Returns:
        - internet: whether general internet is reachable
        - openai: whether OpenAI API is reachable
        - ollama: whether Ollama is running locally
    """
    # Run all checks concurrently
    internet, openai, ollama = await asyncio.gather(
        _check_internet(),
        _check_openai(),
        _check_ollama(),
        return_exceptions=True,
    )

    return {
        "internet": bool(internet) if not isinstance(internet, Exception) else False,
        "openai": bool(openai) if not isinstance(openai, Exception) else False,
        "ollama": bool(ollama) if not isinstance(ollama, Exception) else False,
    }
