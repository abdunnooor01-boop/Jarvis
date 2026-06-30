"""Tests for the LLM service."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.services.llm import OpenAIProvider


@pytest.mark.asyncio
async def test_openai_provider_no_api_key() -> None:
    """Test that OpenAI provider initialization fails gracefully."""
    with patch("app.services.llm.settings.openai_api_key", None):
        with pytest.raises(Exception):
            provider = OpenAIProvider()
            _ = provider.client  # Should fail without API key


@pytest.mark.asyncio
async def test_llm_service_no_providers() -> None:
    """Test LLMService when no providers are configured."""
    from app.services.llm import LLMService

    with patch("app.services.llm.settings.openai_api_key", None):
        with patch("app.services.llm.settings.anthropic_api_key", None):
            with patch("app.services.llm.settings.gemini_api_key", None):
                service = LLMService()
                with pytest.raises(RuntimeError, match="No LLM providers configured"):
                    service.get_provider()