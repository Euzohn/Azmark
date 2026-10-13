"""LLM provider abstraction (spec #36, #66).

Business code never binds to a specific model vendor. A provider normalizes the
chat-completions contract (messages + optional tools -> text + optional tool
calls); new vendors implement this interface and register in the factory.

Messages may contain multimodal content (text + image_url) for vision-capable
models (spec #31). Streaming is supported via ``chat_stream`` which yields
``StreamDelta`` chunks.
"""

import json
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
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


@dataclass
class StreamDelta:
    """A chunk from a streaming response.

    ``content`` is a text fragment yielded incrementally. ``tool_calls`` is
    set only on the final delta when the response contained tool calls.
    """

    content: str = ""
    tool_calls: list[LLMToolCall] | None = None


class LLMProvider(ABC):
    """Normalized chat-completions provider (spec #36)."""

    @abstractmethod
    async def chat(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float | None = None,
    ) -> LLMResponse:
        """Complete a turn. ``tools`` uses the OpenAI tool schema."""
        raise NotImplementedError

    async def chat_stream(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float | None = None,
    ) -> AsyncGenerator[StreamDelta, None]:
        """Stream a turn. Yield ``StreamDelta`` chunks.

        Content fragments arrive as deltas with ``content`` set. If the
        response includes tool calls, a final delta with ``tool_calls`` is
        yielded after all content. Override in subclasses that support it.
        """
        raise NotImplementedError("Streaming not supported by this provider")


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

    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _payload(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        temperature: float | None,
        stream: bool = False,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature if temperature is not None else 0.2,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        if stream:
            payload["stream"] = True
        return payload

    async def chat(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float | None = None,
    ) -> LLMResponse:
        headers = self._headers()
        payload = self._payload(messages=messages, tools=tools, temperature=temperature)

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

    async def chat_stream(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float | None = None,
    ) -> AsyncGenerator[StreamDelta, None]:
        headers = self._headers()
        payload = self._payload(
            messages=messages, tools=tools, temperature=temperature, stream=True
        )

        # Accumulate tool-call fragments by index (OpenAI streams them in pieces)
        tc_acc: dict[int, dict[str, str]] = {}

        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
            async with client.stream(
                "POST", self._endpoint(), headers=headers, json=payload
            ) as response:
                try:
                    response.raise_for_status()
                except httpx.HTTPStatusError as exc:
                    raise LLMProviderError(f"LLM stream failed ({response.status_code})") from exc

                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                    except (ValueError, TypeError):
                        continue
                    try:
                        delta = chunk["choices"][0]["delta"]
                    except (KeyError, IndexError):
                        continue

                    content = delta.get("content")
                    if content:
                        yield StreamDelta(content=content)

                    for tc in delta.get("tool_calls") or []:
                        idx = tc.get("index", 0)
                        if idx not in tc_acc:
                            tc_acc[idx] = {"id": "", "name": "", "arguments": ""}
                        if tc.get("id"):
                            tc_acc[idx]["id"] = tc["id"]
                        fn = tc.get("function", {})
                        if fn.get("name"):
                            tc_acc[idx]["name"] = fn["name"]
                        if fn.get("arguments"):
                            tc_acc[idx]["arguments"] += fn["arguments"]

        if tc_acc:
            tool_calls: list[LLMToolCall] = []
            for idx in sorted(tc_acc):
                tc = tc_acc[idx]
                try:
                    args = json.loads(tc["arguments"]) if tc["arguments"] else {}
                except (ValueError, TypeError):
                    args = {}
                tool_calls.append(LLMToolCall(id=tc["id"], name=tc["name"], arguments=args))
            yield StreamDelta(tool_calls=tool_calls)


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
