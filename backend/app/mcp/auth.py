"""Bearer authentication for the MCP endpoint (spec #33, #57, #69).

MCP clients are long-lived processes, so the only accepted credential is a
personal access token (``azm_...``). Browser session JWTs stay web-only: they
expire in days and must never be pasted into an agent's config file.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass

from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.config import settings
from app.core.rate_limit import access_token_limiter
from app.core.security import PAT_PREFIX
from app.mcp import db as mcp_db
from app.services.access_token import AccessTokenService


@dataclass(frozen=True, slots=True)
class MCPIdentity:
    """Who is calling — always derived from the presented token (spec #57)."""

    user_id: uuid.UUID
    token_id: uuid.UUID
    token_name: str
    scope: str


class MCPAuthMiddleware:
    """Reject anything that is not a live personal access token."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        secret = _bearer(scope)
        if secret is None:
            await _reject(send, 401, "Missing bearer token")
            return
        if not secret.startswith(PAT_PREFIX):
            await _reject(send, 401, "MCP requires a personal access token (azm_...)")
            return

        with mcp_db.session_scope() as db:
            resolved = AccessTokenService(db).authenticate(secret)
            if resolved is None:
                await _reject(send, 401, "Invalid, expired or revoked token")
                return
            user, token = resolved

            limited = settings.pat_rate_limit_per_minute > 0
            if limited and not access_token_limiter.allow(str(token.id)):
                await _reject(send, 429, "Too many requests", retry_after=60)
                return

            identity = MCPIdentity(
                user_id=user.id,
                token_id=token.id,
                token_name=token.name,
                scope=token.scope,
            )

        # Tool handlers read this from ``ctx.request.state``; audit entries pick
        # it up too, so the user can tell which agent acted (spec #75).
        state = scope.setdefault("state", {})
        state["mcp_identity"] = identity

        await self.app(scope, receive, send)


def _bearer(scope: Scope) -> str | None:
    for name, value in scope["headers"]:
        if name.lower() != b"authorization":
            continue
        scheme, _, secret = value.decode("latin-1").strip().partition(" ")
        if scheme.lower() == "bearer" and secret.strip():
            return secret.strip()
        return None
    return None


async def _reject(
    send: Send,
    status: int,
    detail: str,
    *,
    retry_after: int | None = None,
) -> None:
    headers = [(b"content-type", b"application/json")]
    if status == 401:
        headers.append((b"www-authenticate", b'Bearer realm="azmark"'))
    if retry_after is not None:
        headers.append((b"retry-after", str(retry_after).encode()))
    body = json.dumps({"error": detail}).encode()
    await send({"type": "http.response.start", "status": status, "headers": headers})
    await send({"type": "http.response.body", "body": body})
