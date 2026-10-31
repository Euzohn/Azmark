import hashlib
import secrets
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

from app.core.config import settings

# Personal access tokens (spec #85) are prefixed so the auth layer can tell
# them apart from JWT session tokens before doing any decoding work.
PAT_PREFIX = "azm_"
PAT_PREFIX_LENGTH = 12


def generate_access_token() -> str:
    """Create a high-entropy secret. 32 random bytes → 43 URL-safe characters."""
    return f"{PAT_PREFIX}{secrets.token_urlsafe(32)}"


def hash_access_token(token: str) -> str:
    """SHA-256 is enough: the secret itself has 256 bits of entropy.

    Unlike passwords there is no dictionary to attack, so a slow KDF would only
    add latency to every agent request.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def access_token_prefix(token: str) -> str:
    """Short, non-secret fingerprint shown in the token list."""
    return token[:PAT_PREFIX_LENGTH]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(subject: str) -> str:
    expire = datetime.now(UTC) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_access_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except jwt.PyJWTError:
        return None
    subject = payload.get("sub")
    return subject if isinstance(subject, str) else None


def hash_ip(ip: str | None) -> str | None:
    """Salted hash so raw client IPs are never stored (spec #47)."""
    if not ip:
        return None
    return hashlib.sha256(f"{settings.secret_key}:{ip}".encode()).hexdigest()
