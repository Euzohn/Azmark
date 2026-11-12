"""Brute-force budgets on the anonymous auth routes (spec #70).

The in-process limiters are keyed by client IP, and every TestClient request
shares one IP, so these tests shrink the window via the limiter instance
itself (conftest resets the buckets between tests).
"""

from app.core.config import settings
from app.core.rate_limit import login_limiter, register_limiter
from tests.conftest import seed_system_settings


def test_login_returns_429_after_budget(client, monkeypatch):
    monkeypatch.setattr(login_limiter, "limit", 3)
    for _ in range(3):
        response = client.post(
            "/api/v1/auth/login", json={"username": "ghost", "password": "wrongpass"}
        )
        assert response.status_code == 401
    response = client.post(
        "/api/v1/auth/login", json={"username": "ghost", "password": "wrongpass"}
    )
    assert response.status_code == 429
    assert response.headers.get("Retry-After") == "60"


def test_login_budget_is_shared_across_usernames(client, monkeypatch):
    """Password spraying rotates usernames but shares one client-IP window."""
    monkeypatch.setattr(login_limiter, "limit", 4)
    for i in range(4):
        response = client.post(
            "/api/v1/auth/login", json={"username": f"spray{i}", "password": "wrong"}
        )
        assert response.status_code == 401
    response = client.post("/api/v1/auth/login", json={"username": "spray4", "password": "wrong"})
    assert response.status_code == 429


def test_login_limit_disabled_by_setting(client, monkeypatch):
    monkeypatch.setattr(settings, "login_rate_limit_per_minute", 0)
    for _ in range(12):
        response = client.post(
            "/api/v1/auth/login", json={"username": "ghost", "password": "wrongpass"}
        )
        assert response.status_code == 401


def test_register_returns_429_after_budget(client, monkeypatch):
    monkeypatch.setattr(register_limiter, "limit", 2)
    for i in range(2):
        response = client.post(
            "/api/v1/auth/register",
            json={"username": f"spamreg{i}", "password": "secret123"},
        )
        assert response.status_code == 201, response.text
    response = client.post(
        "/api/v1/auth/register",
        json={"username": "spamreg2", "password": "secret123"},
    )
    assert response.status_code == 429
    assert response.headers.get("Retry-After") == "60"


def test_register_failed_captcha_attempts_consume_budget(client, db, monkeypatch):
    """Rejected attempts also count, so captcha-answer guessing is capped too."""
    seed_system_settings(db, registration_captcha_enabled=True)
    monkeypatch.setattr(register_limiter, "limit", 2)

    challenge = client.get("/api/v1/auth/captcha").json()
    a, _, b = challenge["question"].split()
    wrong_answer = str(int(a) + int(b) + 1)
    payload = {
        "username": "capuser",
        "password": "secret123",
        "captcha_token": challenge["token"],
        "captcha_answer": wrong_answer,
    }
    for _ in range(2):
        response = client.post("/api/v1/auth/register", json=payload)
        assert response.status_code == 400, response.text
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 429
    assert response.headers.get("Retry-After") == "60"


def test_register_limit_disabled_by_setting(client, monkeypatch):
    monkeypatch.setattr(settings, "register_rate_limit_per_minute", 0)
    for i in range(6):
        response = client.post(
            "/api/v1/auth/register",
            json={"username": f"spamoff{i}", "password": "secret123"},
        )
        assert response.status_code == 201, response.text
