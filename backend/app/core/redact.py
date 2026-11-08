"""Secret redaction for logs and error strings (spec #45, #75, #96).

Provider API keys travel in different channels — AviationStack puts them in
the URL query string, others use headers or POST bodies. When an HTTP client
raises (e.g. ``httpx.HTTPStatusError``), its message embeds the full request
URL, so logging the exception verbatim would write the user's plaintext key
into server logs. Every place that logs an exception raised around a provider
call must pass the message through :func:`redact_secrets` first.
"""

from __future__ import annotations

import re

# Query-parameter names that carry credentials. Matched case-insensitively
# as ``?name=value`` or ``&name=value`` up to the next delimiter.
_SECRET_QUERY_PARAMS = (
    "access_key",
    "api_key",
    "api-key",
    "apikey",
    "key",
    "token",
    "access_token",
    "refresh_token",
    "id_token",
    "secret",
    "client_secret",
    "secret_key",
    "password",
    "passwd",
    "pwd",
    "signature",
    "sig",
    "auth",
    "authorization",
    "credential",
    "apikey",
)

_QUERY_PARAM_RE = re.compile(
    r"(?i)([?&](?:" + "|".join(re.escape(p) for p in _SECRET_QUERY_PARAMS) + r")=)([^&#\s'\"<>]+)"
)
# ``Authorization: Bearer xxx`` / ``Bearer xxx`` wherever it appears.
_BEARER_RE = re.compile(r"(?i)(bearer\s+)([A-Za-z0-9\-._~+/]+=*)")
# Header forms rendered into exception text: ``X-API-Key: value``. Restricted to
# a ``:`` separator so it cannot collide with ``access_key=…`` query params
# (those use ``=`` and are handled above).
_KEY_HEADER_RE = re.compile(r"(?i)(\b(?:x-)?(?:api|auth|access|subscription)[-_]?key\s*:\s*)(\S+)")

_REDACTED = "[REDACTED]"


def redact_secrets(text: str) -> str:
    """Mask credential-looking substrings in ``text``.

    Only patterns that plausibly carry secrets are touched (query params,
    bearer tokens, key headers); flight numbers, dates and URLs survive
    intact so the log line stays useful for debugging.
    """
    redacted = _QUERY_PARAM_RE.sub(r"\g<1>" + _REDACTED, text)
    redacted = _BEARER_RE.sub(r"\g<1>" + _REDACTED, redacted)
    redacted = _KEY_HEADER_RE.sub(r"\g<1>" + _REDACTED, redacted)
    return redacted


def redact_exception(exc: BaseException) -> str:
    """Return a repr of ``exc`` safe to log (secrets masked)."""
    return redact_secrets(repr(exc))
