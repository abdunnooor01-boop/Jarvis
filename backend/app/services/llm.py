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

            # OpenAI streams tool-call fragments: the same call index appears
            # across multiple deltas with partial `arguments` text. Accumulate
            # by index and yield complete calls once the stream ends.
            tool_calls_acc: dict[int, dict[str, str]] = {}

            async for chunk in stream:
                if not chunk.choices:
                    continue

                delta = chunk.choices[0].delta

                if delta.content:
                    yield {"type": "content", "content": delta.content}

                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        idx = tc.index if tc.index is not None else 0
                        acc = tool_calls_acc.setdefault(
                            idx, {"id": "", "name": "", "arguments": ""}
                        )
                        if tc.id:
                            acc["id"] = tc.id
                        if tc.function:
                            if tc.function.name:
                                acc["name"] = tc.function.name
                            if tc.function.arguments:
                                acc["arguments"] += tc.function.arguments

            # Yield complete tool calls (in order) after the stream ends
            for idx in sorted(tool_calls_acc):
                acc = tool_calls_acc[idx]
                if acc["name"]:
                    yield {
                        "type": "tool_call",
                        "id": acc["id"] or f"call_{idx}",
                        "name": acc["name"],
                        "arguments": acc["arguments"],
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


class OllamaProvider(LLMProvider):
    """Ollama local LLM provider — runs models locally via Ollama API.

    Supports the same interface as OpenAIProvider but uses Ollama's
    OpenAI-compatible API endpoint. Requires Ollama to be running locally.
    """

    def __init__(self) -> None:
        self.base_url = settings.ollama_base_url.rstrip("/")
        self.model = settings.ollama_model
        self._http_client: Any = None

    async def _get_client(self) -> Any:
        """Lazy-initialize the HTTP client."""
        if self._http_client is None:
            import httpx

            self._http_client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=120.0,
            )
        return self._http_client

    async def _check_available(self) -> bool:
        """Check if Ollama is reachable."""
        try:
            client = await self._get_client()
            resp = await client.get("/api/tags")
            return resp.status_code == 200
        except Exception:
            return False

    async def stream_chat(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        try:
            available = await self._check_available()
            if not available:
                yield {
                    "type": "error",
                    "content": (
                        f"Ollama is not reachable at {self.base_url}. "
                        "Make sure Ollama is running (ollama serve) "
                        "and the model is pulled (ollama pull llama3)."
                    ),
                }
                return

            client = await self._get_client()
            payload: dict[str, Any] = {
                "model": self.model,
                "messages": messages,
                "stream": True,
            }

            # Ollama supports OpenAI-compatible tool calling format
            if tools:
                payload["tools"] = tools

            async with client.stream(
                "POST",
                "/api/chat",
                json=payload,
            ) as response:
                if response.status_code != 200:
                    error_text = await response.aread()
                    yield {
                        "type": "error",
                        "content": f"Ollama error ({response.status_code}): {error_text[:200]}",
                    }
                    return

                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        import json

                        chunk = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    if "message" in chunk:
                        msg = chunk["message"]
                        content = msg.get("content", "")
                        if content:
                            yield {"type": "content", "content": content}

                        if msg.get("tool_calls"):
                            for tc in msg["tool_calls"]:
                                yield {
                                    "type": "tool_call",
                                    "id": tc.get("id", ""),
                                    "name": tc["function"]["name"],
                                    "arguments": tc["function"]["arguments"],
                                }

                    if chunk.get("done"):
                        break

        except Exception as e:
            logger.error("Ollama streaming error", error=str(e))
            yield {
                "type": "error",
                "content": f"Ollama error: {e!s}",
            }

    async def chat(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        try:
            available = await self._check_available()
            if not available:
                return {
                    "content": "",
                    "role": "assistant",
                    "error": (
                        f"Ollama is not reachable at {self.base_url}. "
                        "Make sure Ollama is running (ollama serve) "
                        "and the model is pulled (ollama pull llama3)."
                    ),
                }

            client = await self._get_client()
            payload: dict[str, Any] = {
                "model": self.model,
                "messages": messages,
                "stream": False,
            }

            if tools:
                payload["tools"] = tools

            response = await client.post("/api/chat", json=payload)
            if response.status_code != 200:
                return {
                    "content": "",
                    "role": "assistant",
                    "error": f"Ollama error ({response.status_code}): {response.text[:200]}",
                }

            data = response.json()
            msg = data.get("message", {})

            result: dict[str, Any] = {
                "content": msg.get("content", ""),
                "role": msg.get("role", "assistant"),
            }

            if msg.get("tool_calls"):
                result["tool_calls"] = [
                    {
                        "id": tc.get("id", ""),
                        "name": tc["function"]["name"],
                        "arguments": tc["function"]["arguments"],
                    }
                    for tc in msg["tool_calls"]
                ]

            return result

        except Exception as e:
            logger.error("Ollama chat error", error=str(e))
            return {"content": "", "role": "assistant", "error": str(e)}

    async def list_models(self) -> list[dict[str, Any]]:
        """List available models from the Ollama API."""
        try:
            client = await self._get_client()
            resp = await client.get("/api/tags")
            if resp.status_code == 200:
                data = resp.json()
                return data.get("models", [])
            return []
        except Exception as e:
            logger.error("Failed to list Ollama models", error=str(e))
            return []


class LLMService:
    """Orchestrates LLM providers via the Strategy pattern."""

    def __init__(self) -> None:
        self._providers: dict[str, LLMProvider] = {}
        self._default_provider: str = settings.llm_provider or "openai"
        self._initialize_providers()

    def _initialize_providers(self) -> None:
        """Register available providers based on configuration."""
        if settings.openai_api_key:
            self._providers["openai"] = OpenAIProvider()
            logger.info("OpenAI provider registered")

        if settings.anthropic_api_key:
            self._providers["anthropic"] = AnthropicProvider()
            logger.info("Anthropic provider registered")

        if settings.gemini_api_key:
            self._providers["gemini"] = GeminiProvider()
            logger.info("Gemini provider registered")

        # Ollama is always available — no API key needed
        if settings.ollama_base_url:
            self._providers["ollama"] = OllamaProvider()
            logger.info(
                "Ollama provider registered",
                base_url=settings.ollama_base_url,
                model=settings.ollama_model,
            )

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
