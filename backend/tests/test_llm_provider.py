"""OpenAI-compatible provider: reasoning (thinking mode) parsing."""

import asyncio

import httpx

from app.providers.llm import OpenAICompatibleProvider


class _FakeStreamResponse:
    def __init__(self, lines: list[str]) -> None:
        self._lines = lines
        self.status_code = 200

    def raise_for_status(self) -> None:
        return None

    async def aiter_lines(self):
        for line in self._lines:
            yield line


class _FakeStreamContext:
    def __init__(self, response: _FakeStreamResponse) -> None:
        self._response = response

    async def __aenter__(self) -> _FakeStreamResponse:
        return self._response

    async def __aexit__(self, *_exc) -> bool:
        return False


class _FakeClient:
    """Stands in for httpx.AsyncClient; serves either a stream or one JSON reply."""

    def __init__(self, *, lines: list[str] | None = None, payload: dict | None = None) -> None:
        self._lines = lines or []
        self._payload = payload or {}

    async def __aenter__(self) -> "_FakeClient":
        return self

    async def __aexit__(self, *_exc) -> bool:
        return False

    def stream(self, *_args, **_kwargs) -> _FakeStreamContext:
        return _FakeStreamContext(_FakeStreamResponse(self._lines))

    async def post(self, *_args, **_kwargs) -> httpx.Response:
        return httpx.Response(
            200, json=self._payload, request=httpx.Request("POST", "https://fake.local")
        )


def _provider() -> OpenAICompatibleProvider:
    return OpenAICompatibleProvider(
        base_url="https://api.deepseek.com/v1", model="deepseek-flash", api_key="k"
    )


def test_chat_stream_parses_reasoning_content(monkeypatch):
    lines = [
        'data: {"choices":[{"delta":{"reasoning_content":"step 1"}}]}',
        'data: {"choices":[{"delta":{"reasoning_content":" step 2"}}]}',
        'data: {"choices":[{"delta":{"content":"Hello"}}]}',
        "data: [DONE]",
    ]
    monkeypatch.setattr(
        "app.providers.llm.httpx.AsyncClient", lambda **_kwargs: _FakeClient(lines=lines)
    )

    async def run():
        return [
            delta
            async for delta in _provider().chat_stream(messages=[{"role": "user", "content": "hi"}])
        ]

    deltas = asyncio.run(run())
    assert "".join(delta.reasoning for delta in deltas) == "step 1 step 2"
    assert "".join(delta.content for delta in deltas) == "Hello"


def test_chat_parses_reasoning_content(monkeypatch):
    payload = {"choices": [{"message": {"content": "Hi", "reasoning_content": "thinking it over"}}]}
    monkeypatch.setattr(
        "app.providers.llm.httpx.AsyncClient", lambda **_kwargs: _FakeClient(payload=payload)
    )

    result = asyncio.run(_provider().chat(messages=[{"role": "user", "content": "hi"}]))
    assert result.content == "Hi"
    assert result.reasoning == "thinking it over"
