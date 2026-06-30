"""LLM integration service with multi-provider support (Strategy pattern)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from typing import Any

from app.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    async def stream_chat(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Stream chat completion. Yields content chunks, tool calls, or errors."""
        ...

    @abstractmethod
    async def chat(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Non-streaming chat completion. Returns the full response."""
        ...


class OpenAIProvider(LLMProvider):
    """OpenAI (GPT-4o, etc.) provider implementation."""

    def __init__(self) -> None:
        import openai

        self.client = openai.AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_model

    async def stream_chat(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        try:
            kwargs: dict[str, Any] = {
                "model": self.model,
                "messages": messages,
                "stream": True,
                "stream_options": {"include_usage": True},
            }
            if tools:
                kwargs["tools"] = tools
                kwargs["tool_choice"] = "auto"

            stream = await self.client.chat.completions.create(**kwargs)

            async for chunk in stream:
                if not chunk.choices:
                    continue

                delta = chunk.choices[0].delta

                if delta.content:
                    yield {"type": "content", "content": delta.content}

                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        if tc.function:
                            yield {
                                "type": "tool_call",
                                "id": tc.id,
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            }

        except Exception as e:
            logger.error("OpenAI streaming error", error=str(e))
            yield {"type": "error", "content": f"OpenAI error: {e!s}"}

    async def chat(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        try:
            kwargs: dict[str, Any] = {
                "model": self.model,
                "messages": messages,
            }
            if tools:
                kwargs["tools"] = tools
                kwargs["tool_choice"] = "auto"

            response = await self.client.chat.completions.create(**kwargs)
            choice = response.choices[0]

            result: dict[str, Any] = {
                "content": choice.message.content or "",
                "role": choice.message.role,
            }

            if choice.message.tool_calls:
                result["tool_calls"] = [
                    {
                        "id": tc.id,
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    }
                    for tc in choice.message.tool_calls
                ]

            return result

        except Exception as e:
            logger.error("OpenAI chat error", error=str(e))
            return {"content": "", "role": "assistant", "error": str(e)}


class AnthropicProvider(LLMProvider):
    """Anthropic (Claude) provider implementation — placeholder for Phase 1."""

    def __init__(self) -> None:
        self.api_key = settings.anthropic_api_key

    async def stream_chat(
        self,
        messages: list[dict[str, str]],  # noqa: ARG002
        tools: list[dict[str, Any]] | None = None,  # noqa: ARG002
    ) -> AsyncGenerator[dict[str, Any], None]:
        yield {"type": "content", "content": "[Anthropic provider not yet implemented]"}
        yield {"type": "done"}

    async def chat(
        self,
        messages: list[dict[str, str]],  # noqa: ARG002
        tools: list[dict[str, Any]] | None = None,  # noqa: ARG002
    ) -> dict[str, Any]:
        return {"content": "[Anthropic provider not yet implemented]", "role": "assistant"}


class GeminiProvider(LLMProvider):
    """Google Gemini provider implementation — placeholder for Phase 1."""

    def __init__(self) -> None:
        self.api_key = settings.gemini_api_key

    async def stream_chat(
        self,
        messages: list[dict[str, str]],  # noqa: ARG002
        tools: list[dict[str, Any]] | None = None,  # noqa: ARG002
    ) -> AsyncGenerator[dict[str, Any], None]:
        yield {"type": "content", "content": "[Gemini provider not yet implemented]"}
        yield {"type": "done"}

    async def chat(
        self,
        messages: list[dict[str, str]],  # noqa: ARG002
        tools: list[dict[str, Any]] | None = None,  # noqa: ARG002
    ) -> dict[str, Any]:
        return {"content": "[Gemini provider not yet implemented]", "role": "assistant"}


class LLMService:
    """Orchestrates LLM providers via the Strategy pattern."""

    def __init__(self) -> None:
        self._providers: dict[str, LLMProvider] = {}
        self._default_provider: str = "openai"
        self._initialize_providers()

    def _initialize_providers(self) -> None:
        """Register available providers based on configured API keys."""
        if settings.openai_api_key:
            self._providers["openai"] = OpenAIProvider()
            logger.info("OpenAI provider registered")

        if settings.anthropic_api_key:
            self._providers["anthropic"] = AnthropicProvider()
            logger.info("Anthropic provider registered")

        if settings.gemini_api_key:
            self._providers["gemini"] = GeminiProvider()
            logger.info("Gemini provider registered")

    def get_provider(self, provider: str | None = None) -> LLMProvider:
        """Get a provider by name, falling back to default."""
        name = provider or self._default_provider
        if name not in self._providers:
            if not self._providers:
                raise RuntimeError("No LLM providers configured")
            name = list(self._providers.keys())[0]
        return self._providers[name]

    async def stream_chat(
        self,
        messages: list[dict[str, str]],
        provider: str | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Stream a chat completion from the specified or default provider."""
        p = self.get_provider(provider)
        async for chunk in p.stream_chat(messages, tools):
            yield chunk

    async def chat(
        self,
        messages: list[dict[str, str]],
        provider: str | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Non-streaming chat completion."""
        p = self.get_provider(provider)
        return await p.chat(messages, tools)


# Singleton
_llm_service: LLMService | None = None


def get_llm_service() -> LLMService:
    """Get or create the LLM service singleton."""
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service
