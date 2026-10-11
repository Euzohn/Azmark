"""LLM provider abstraction (spec #36, #66).

Business code never binds to a specific model vendor. A provider normalizes the
chat-completions contract (messages + optional tools -> text + optional tool
calls); new vendors implement this interface and register in the factory.
"""

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import httpx


@dataclass
class LLMToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class LLMResponse:
    content: str | None = None
    tool_calls: list[LLMToolCall] = field(default_factory=list)


class LLMProvider(ABC):
    """Normalized chat-completions provider (spec #36)."""

    @abstractmethod
    async def chat(
        self,
        *,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float | None = None,
    ) -> LLMResponse:
        """Complete a turn. `tools` uses the OpenAI tool schema."""
        raise NotImplementedError


class OpenAICompatibleProvider(LLMProvider):
    """OpenAI-compatible /chat/completions endpoint (OpenAI, Ollama, Compatible, Custom).

    Raw key is never logged; failures surface as LLMProviderError so the agent
    layer can degrade gracefully instead of leaking credentials (spec #45, #96).
    """

    def __init__(self, *, base_url: str, model: str, api_key: str | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key

    def _endpoint(self) -> str:
        return f"{self.base_url}/chat/completions"

    async def chat(
        self,
        *,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float | None = None,
    ) -> LLMResponse:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature if temperature is not None else 0.2,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:
            response = await client.post(self._endpoint(), headers=headers, json=payload)
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise LLMProviderError(f"LLM request failed ({response.status_code})") from exc
            data = response.json()

        try:
            message = data["choices"][0]["message"]
        except (KeyError, IndexError) as exc:
            raise LLMProviderError("LLM returned an unreadable response") from exc

        content = message.get("content")
        tool_calls: list[LLMToolCall] = []
        for call in message.get("tool_calls") or []:
            arguments = call.get("function", {}).get("arguments", "{}")
            try:
                parsed = json.loads(arguments) if arguments else {}
            except (TypeError, ValueError):
                parsed = {}
            tool_calls.append(
                LLMToolCall(
                    id=call.get("id", ""),
                    name=call.get("function", {}).get("name", ""),
                    arguments=parsed,
                )
            )
        return LLMResponse(content=content or None, tool_calls=tool_calls)


class LLMProviderError(Exception):
    """Raised when an upstream LLM call fails (never includes secrets)."""


DEFAULT_BASE_URLS: dict[str, str] = {
    "openai": "https://api.openai.com/v1",
    "ollama": "http://localhost:11434/v1",
}


def build_llm_provider(
    *,
    provider: str,
    model: str,
    base_url: str | None,
    api_key: str | None,
) -> LLMProvider:
    """Map a stored provider string to a concrete provider (spec #36).

    Every registered value goes through the OpenAI-compatible transport so the
    app never hard-codes a single vendor; a custom base_url is honored as-is.
    """
    url = base_url or DEFAULT_BASE_URLS.get(provider)
    if not url:
        raise LLMProviderError(f"Provider '{provider}' requires a base URL")
    return OpenAICompatibleProvider(base_url=url, model=model, api_key=api_key)
