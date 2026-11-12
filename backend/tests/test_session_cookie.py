"""HttpOnly session cookie for the web UI (spec #4.3)."""

from app.core.config import settings
from app.core.security import PAT_PREFIX, SESSION_COOKIE_NAME
from tests.conftest import register_and_login


def _register_and_login_raw(client, username: str) -> dict:
    register_and_login(client, username)
    return {"username": username}


def test_login_sets_http_only_session_cookie(client):
    _register_and_login_raw(client, "cookie_attr")
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "cookie_attr", "password": "secret123"},
    )
    assert response.status_code == 200, response.text
    set_cookie = response.headers["set-cookie"]
    assert set_cookie.startswith(f"{SESSION_COOKIE_NAME}=")
    assert "HttpOnly" in set_cookie
    assert "SameSite=lax" in set_cookie
    assert "Path=/" in set_cookie
    # Plain-HTTP deployments must keep working until the operator flips this.
    assert "Secure" not in set_cookie


def test_session_cookie_secure_flag(client, monkeypatch):
    monkeypatch.setattr(settings, "session_cookie_secure", True)
    _register_and_login_raw(client, "cookie_secure")
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "cookie_secure", "password": "secret123"},
    )
    assert response.status_code == 200
    assert "Secure" in response.headers["set-cookie"]


def test_cookie_authenticates_without_header(client):
    """The cookie jar alone must authenticate: the web UI sends no Bearer."""
    register_and_login(client, "cookie_jar")
    # The TestClient jar now holds azmark_session; this request carries no
    # Authorization header at all.
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 200, response.text
    assert response.json()["username"] == "cookie_jar"


def test_pat_is_never_accepted_from_a_cookie(client):
    # A PAT-shaped value in the cookie slot must not authenticate; PATs are
    # Bearer-header credentials for agents, not browser sessions (spec #85).
    response = client.get(
        "/api/v1/auth/me",
        cookies={SESSION_COOKIE_NAME: f"{PAT_PREFIX}forged-secret"},
    )
    assert response.status_code == 401


def test_logout_clears_session_cookie(client):
    register_and_login(client, "cookie_out")
    assert client.cookies.get(SESSION_COOKIE_NAME) is not None
    response = client.post("/api/v1/auth/logout")
    assert response.status_code == 204
    expiry = response.headers["set-cookie"]
    assert expiry.startswith(f"{SESSION_COOKIE_NAME}=")
    assert "Max-Age=0" in expiry  # expired — the jar drops it
    # After the jar processed the expiry, cookie-only requests are anonymous.
    assert client.get("/api/v1/auth/me").status_code == 401


def test_cookie_with_wrong_signature_rejected(client):
    response = client.get(
        "/api/v1/auth/me",
        cookies={SESSION_COOKIE_NAME: "definitely-not-a-jwt"},
    )
    assert response.status_code == 401
