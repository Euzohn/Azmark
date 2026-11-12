"""Stateless arithmetic challenge for the public registration form.

The token embeds the operands and an expiry, signed with an HMAC derived from
SECRET_KEY. Nothing is stored server-side, so this works with any number of
workers behind a load balancer. A one-operation challenge stops scripted bulk
registration (which is what open sign-up attracts) without an external captcha
service or tracking; it is not a click farm defence, and is an explicit
trade-off for a self-hosted, privacy-first product (spec #2.6, #60).
"""

import base64
import hashlib
import hmac
import json
import secrets
import time

import httpx

from app.core.config import settings

CAPTCHA_TTL_SECONDS = 300

CAPTCHA_PROVIDER_ARITHMETIC = "arithmetic"
CAPTCHA_PROVIDER_TURNSTILE = "turnstile"

TURNSTILE_SITEVERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


def _key() -> bytes:
    return hashlib.sha256(f"azmark-captcha:{settings.secret_key}".encode()).digest()


def create_captcha(ttl_seconds: int = CAPTCHA_TTL_SECONDS) -> tuple[str, str]:
    """Return ``(token, question)``. The question uses digits only, so it reads
    the same in every locale (e.g. ``"7 + 5"``)."""
    a = secrets.randbelow(9) + 1
    b = secrets.randbelow(9) + 1
    payload = {"a": a, "b": b, "exp": int(time.time()) + ttl_seconds}
    raw = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()
    signature = hmac.new(_key(), raw.encode(), hashlib.sha256).hexdigest()
    return f"{raw}.{signature}", f"{a} + {b}"


def verify_captcha(token: str, answer: str) -> bool:
    """True only when the token is untampered, unexpired and answered correctly."""
    try:
        raw, signature = token.rsplit(".", 1)
    except ValueError:
        return False
    expected = hmac.new(_key(), raw.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return False
    try:
        payload = json.loads(base64.urlsafe_b64decode(raw.encode()))
    except (ValueError, json.JSONDecodeError):
        return False
    if int(payload.get("exp", 0)) < time.time():
        return False
    try:
        given = int(str(answer).strip())
    except ValueError:
        return False
    return given == int(payload["a"]) + int(payload["b"])


def verify_turnstile(token: str, secret: str, remote_ip: str | None = None) -> bool:
    """Verify a Cloudflare Turnstile response token server-side.

    Always returns False on network or protocol errors — failing open would
    defeat the point of the challenge (spec #60).
    """
    try:
        response = httpx.post(
            TURNSTILE_SITEVERIFY_URL,
            data={
                "secret": secret,
                "response": token,
                **({"remoteip": remote_ip} if remote_ip else {}),
            },
            timeout=10.0,
        )
        payload = response.json()
    except (httpx.HTTPError, ValueError):
        return False
    return bool(payload.get("success"))
