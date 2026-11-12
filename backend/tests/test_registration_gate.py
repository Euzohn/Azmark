"""Registration gate and arithmetic captcha (spec #60)."""

from tests.conftest import register_and_login, seed_system_settings


def test_register_closed_when_settings_row_missing(client, db):
    """Fail-closed: even without a seeded row the door stays shut."""
    from app.models.system_setting import SystemSetting

    existing = db.get(SystemSetting, 1)
    if existing is not None:
        db.delete(existing)
        db.flush()

    response = client.post(
        "/api/v1/auth/register", json={"username": "intruder", "password": "secret123"}
    )
    assert response.status_code == 403


def test_register_open_by_default_in_test_seed(client):
    response = register_and_login(client, "openuser")
    assert "access_token" in response


def test_register_closed_when_disabled(client, db):
    seed_system_settings(db, allow_registration=False)
    response = client.post(
        "/api/v1/auth/register", json={"username": "stranger", "password": "secret123"}
    )
    assert response.status_code == 403
    assert "disabled" in response.json()["detail"].lower()


def test_auth_config_reflects_settings(client, db):
    from app.core.security import encrypt_field
    from app.models.system_setting import TURNSTILE_SECRET_SALT

    response = client.get("/api/v1/auth/config")
    assert response.status_code == 200
    assert response.json() == {
        "allow_registration": True,
        "registration_captcha_enabled": False,
        "captcha_provider": "arithmetic",
        "turnstile_site_key": None,
    }

    # Fully configured Turnstile is advertised as-is.
    row = seed_system_settings(
        db,
        allow_registration=False,
        registration_captcha_enabled=True,
        captcha_provider="turnstile",
        turnstile_site_key="1x00000000000000000000AA",
    )
    row.turnstile_secret_key_enc = encrypt_field(
        TURNSTILE_SECRET_SALT, "1x0000000000000000000000000000000AA"
    )
    db.flush()
    response = client.get("/api/v1/auth/config")
    assert response.json() == {
        "allow_registration": False,
        "registration_captcha_enabled": True,
        "captcha_provider": "turnstile",
        "turnstile_site_key": "1x00000000000000000000AA",
    }

    # A site key without a secret is NOT advertised: the register form must
    # render the arithmetic challenge the register endpoint will enforce.
    row.turnstile_secret_key_enc = None
    db.flush()
    response = client.get("/api/v1/auth/config")
    assert response.json() == {
        "allow_registration": False,
        "registration_captcha_enabled": True,
        "captcha_provider": "arithmetic",
        "turnstile_site_key": None,
    }


def test_captcha_endpoint_returns_signed_challenge(client):
    response = client.get("/api/v1/auth/captcha")
    assert response.status_code == 200
    body = response.json()
    assert body["token"]
    assert " + " in body["question"]


def test_register_requires_valid_captcha_when_enabled(client, db):
    seed_system_settings(db, registration_captcha_enabled=True)

    missing = client.post(
        "/api/v1/auth/register", json={"username": "nobot", "password": "secret123"}
    )
    assert missing.status_code == 400

    wrong = client.post(
        "/api/v1/auth/register",
        json={
            "username": "nobot",
            "password": "secret123",
            "captcha_token": "junk.junk",
            "captcha_answer": "1",
        },
    )
    assert wrong.status_code == 400

    challenge = client.get("/api/v1/auth/captcha").json()
    a, b = (int(part) for part in challenge["question"].split(" + "))
    bad_answer = client.post(
        "/api/v1/auth/register",
        json={
            "username": "nobot",
            "password": "secret123",
            "captcha_token": challenge["token"],
            "captcha_answer": str(a + b + 1),
        },
    )
    assert bad_answer.status_code == 400

    good = client.post(
        "/api/v1/auth/register",
        json={
            "username": "nobot",
            "password": "secret123",
            "captcha_token": challenge["token"],
            "captcha_answer": str(a + b),
        },
    )
    assert good.status_code == 201, good.text


def test_captcha_ignored_when_disabled(client):
    response = client.post(
        "/api/v1/auth/register",
        json={
            "username": "plain",
            "password": "secret123",
            "captcha_token": "junk.junk",
            "captcha_answer": "0",
        },
    )
    assert response.status_code == 201


def test_expired_captcha_rejected(client, db):
    from app.core.captcha import create_captcha

    seed_system_settings(db, registration_captcha_enabled=True)
    token, question = create_captcha(ttl_seconds=-60)
    a, b = (int(part) for part in question.split(" + "))
    response = client.post(
        "/api/v1/auth/register",
        json={
            "username": "late",
            "password": "secret123",
            "captcha_token": token,
            "captcha_answer": str(a + b),
        },
    )
    assert response.status_code == 400


def test_register_duplicate_email_conflict(client, db):
    register_and_login(client, "emailone", "secret123")
    # attach the same email through a second account attempt
    first = client.post(
        "/api/v1/auth/register",
        json={"username": "emailtwo", "password": "secret123", "email": "dup@example.com"},
    )
    assert first.status_code == 201
    second = client.post(
        "/api/v1/auth/register",
        json={"username": "emailthree", "password": "secret123", "email": "dup@example.com"},
    )
    assert second.status_code == 409


def test_turnstile_provider_challenges_registration(client, db, monkeypatch):
    import app.api.routes.auth as auth_routes
    from app.core.security import encrypt_field
    from app.models.system_setting import TURNSTILE_SECRET_SALT

    seen = {}

    def fake_verify(token: str, secret: str, remote_ip: str | None = None) -> bool:
        seen["token"] = token
        seen["secret"] = secret
        return token == "valid-turnstile-token"

    monkeypatch.setattr(auth_routes, "verify_turnstile", fake_verify)
    row = seed_system_settings(
        db,
        registration_captcha_enabled=True,
        captcha_provider="turnstile",
        turnstile_site_key="1x00000000000000000000AA",
    )
    row.turnstile_secret_key_enc = encrypt_field(
        TURNSTILE_SECRET_SALT, "1x0000000000000000000000000000000AA"
    )
    db.flush()

    missing = client.post(
        "/api/v1/auth/register", json={"username": "tnobody", "password": "secret123"}
    )
    assert missing.status_code == 400

    invalid = client.post(
        "/api/v1/auth/register",
        json={"username": "tnobody", "password": "secret123", "captcha_token": "wrong"},
    )
    assert invalid.status_code == 400

    good = client.post(
        "/api/v1/auth/register",
        json={
            "username": "tnobody",
            "password": "secret123",
            "captcha_token": "valid-turnstile-token",
        },
    )
    assert good.status_code == 201, good.text
    assert seen["token"] == "valid-turnstile-token"


def test_turnstile_falls_back_to_arithmetic_without_secret(client, db):
    seed_system_settings(db, registration_captcha_enabled=True, captcha_provider="turnstile")

    challenge = client.get("/api/v1/auth/captcha").json()
    a, b = (int(part) for part in challenge["question"].split(" + "))
    response = client.post(
        "/api/v1/auth/register",
        json={
            "username": "fallback",
            "password": "secret123",
            "captcha_token": challenge["token"],
            "captcha_answer": str(a + b),
        },
    )
    assert response.status_code == 201, response.text


def test_half_configured_turnstile_accepts_arithmetic_registration(client, db):
    """Site key set but secret missing: the effective challenge is arithmetic,
    and /auth/config must agree so the rendered form actually works."""
    seed_system_settings(
        db,
        registration_captcha_enabled=True,
        captcha_provider="turnstile",
        turnstile_site_key="1x00000000000000000000AA",
    )

    config = client.get("/api/v1/auth/config").json()
    assert config["captcha_provider"] == "arithmetic"
    assert config["turnstile_site_key"] is None

    challenge = client.get("/api/v1/auth/captcha").json()
    a, b = (int(part) for part in challenge["question"].split(" + "))
    response = client.post(
        "/api/v1/auth/register",
        json={
            "username": "halfconf",
            "password": "secret123",
            "captcha_token": challenge["token"],
            "captcha_answer": str(a + b),
        },
    )
    assert response.status_code == 201, response.text


def test_turnstile_secret_without_site_key_falls_back_to_arithmetic(client, db):
    """Secret set but site key missing: the widget cannot render, so the
    effective challenge is arithmetic and registration stays open."""
    from app.core.security import encrypt_field
    from app.models.system_setting import TURNSTILE_SECRET_SALT

    row = seed_system_settings(db, registration_captcha_enabled=True, captcha_provider="turnstile")
    row.turnstile_secret_key_enc = encrypt_field(
        TURNSTILE_SECRET_SALT, "1x0000000000000000000000000000000AA"
    )
    db.flush()

    config = client.get("/api/v1/auth/config").json()
    assert config["captcha_provider"] == "arithmetic"
    assert config["turnstile_site_key"] is None

    challenge = client.get("/api/v1/auth/captcha").json()
    a, b = (int(part) for part in challenge["question"].split(" + "))
    response = client.post(
        "/api/v1/auth/register",
        json={
            "username": "noksitekey",
            "password": "secret123",
            "captcha_token": challenge["token"],
            "captcha_answer": str(a + b),
        },
    )
    assert response.status_code == 201, response.text
