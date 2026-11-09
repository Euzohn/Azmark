"""Per-request correlation id middleware (spec #47).

Stamps an opaque ``request_id`` onto ``scope["state"]`` so every audit row a
single request produces can be grouped, and echoes it back as ``X-Request-Id``.
A caller (e.g. a gateway) may supply its own id via the ``X-Request-Id`` header
for cross-service tracing; it is accepted only if it is already a safe token, so
a hostile client cannot smuggle control characters into stored rows or logs.
"""

import re
import uuid

from starlette.types import ASGIApp, Message, Receive, Scope, Send

_REQUEST_ID_HEADER = b"x-request-id"
#: Accept only an already-safe token from the client; anything else is ignored
#: and replaced with a server-generated id (avoids log/header injection, #96).
_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9_.-]{8,64}$")


def _incoming_request_id(scope: Scope) -> str | None:
    for key, value in scope.get("headers", []):
        if key.lower() == _REQUEST_ID_HEADER:
            token = value.decode("latin-1").strip()
            return token if _SAFE_REQUEST_ID.match(token) else None
    return None


class RequestContextMiddleware:
    """Attach ``request_id`` to every HTTP request (REST and MCP alike)."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = _incoming_request_id(scope) or uuid.uuid4().hex
        state = scope.setdefault("state", {})
        state["request_id"] = request_id

        async def send_with_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((_REQUEST_ID_HEADER, request_id.encode("latin-1")))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_id)
