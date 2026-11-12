from sqlalchemy import select

from app.core.security import verify_password
from app.models.audit_log import AuditAction
from app.models.system_setting import SystemSetting
from app.models.user import User, UserRole, UserStatus
from app.services.admin import ensure_admin
from tests.conftest import auth_headers, register_and_login


def _promote(db, username: str) -> User:
    user = db.scalar(select(User).where(User.username == username))
    assert user is not None
    user.role = UserRole.ADMIN
    db.commit()
    db.refresh(user)
    return user


def test_ensure_admin_creates_then_promotes(db):
    user, outcome = ensure_admin(
        db, username="boss", email="boss@example.com", password="secret123"
    )
    assert outcome == "created"
    assert user.role == UserRole.ADMIN
    assert verify_password("secret123", user.password_hash)

    again, outcome = ensure_admin(db, username="boss", password="ignored123")
    assert outcome == "exists"
    assert again.id == user.id
    assert verify_password("secret123", again.password_hash)

    normal = User(username="normal", password_hash=user.password_hash)
    db.add(normal)
    db.commit()

    promoted, outcome = ensure_admin(db, username="normal", password="ignored123")
    assert outcome == "promoted"
    assert promoted.role == UserRole.ADMIN


def test_ensure_admin_can_reset_password(db):
    user, _ = ensure_admin(db, username="resetme", password="oldpass123")
    updated, outcome = ensure_admin(
        db, username="resetme", password="newpass123", reset_password=True
    )
    assert outcome == "updated"
    assert updated.id == user.id
    assert verify_password("newpass123", updated.password_hash)


def test_admin_endpoints_reject_regular_users(client):
    token = register_and_login(client, "plainuser")["access_token"]
    headers = auth_headers(token)

    for path in ("/api/v1/admin/users", "/api/v1/admin/logs", "/api/v1/admin/system"):
        response = client.get(path, headers=headers)
        assert response.status_code == 403


def test_admin_can_list_users_and_change_roles(client, db):
    admin_token = register_and_login(client, "root")["access_token"]
    register_and_login(client, "member")
    _promote(db, "root")

    response = client.get("/api/v1/admin/users", headers=auth_headers(admin_token))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 2
    member = next(item for item in body["items"] if item["username"] == "member")
    assert member["role"] == UserRole.USER

    response = client.patch(
        f"/api/v1/admin/users/{member['id']}",
        json={"role": "ADMIN"},
        headers=auth_headers(admin_token),
    )
    assert response.status_code == 200, response.text
    assert response.json()["role"] == UserRole.ADMIN

    response = client.patch(
        f"/api/v1/admin/users/{member['id']}",
        json={"status": "DISABLED"},
        headers=auth_headers(admin_token),
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == UserStatus.DISABLED


def test_admin_cannot_lock_themselves_out(client, db):
    token = register_and_login(client, "selfroot")["access_token"]
    admin = _promote(db, "selfroot")

    response = client.patch(
        f"/api/v1/admin/users/{admin.id}",
        json={"role": "USER"},
        headers=auth_headers(token),
    )
    assert response.status_code == 400

    response = client.patch(
        f"/api/v1/admin/users/{admin.id}",
        json={"status": "DISABLED"},
        headers=auth_headers(token),
    )
    assert response.status_code == 400


def test_admin_sees_logs_and_system_counts(client, db):
    token = register_and_login(client, "logroot")["access_token"]
    _promote(db, "logroot")
    headers = auth_headers(token)

    client.post(
        "/api/v1/flights",
        json={"origin": "HKG", "destination": "SIN", "service_number": "CX659"},
        headers=headers,
    )

    response = client.get("/api/v1/admin/logs?page_size=100", headers=headers)
    assert response.status_code == 200, response.text
    actions = [item["action"] for item in response.json()["items"]]
    assert "register" in actions
    assert "create_record" in actions

    response = client.get("/api/v1/admin/system", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["users"] == 1
    assert body["records"] == 1
    assert body["admins"] == 1
    assert body["version"]


def test_disabled_users_are_rejected(client, db):
    token = register_and_login(client, "disabled")["access_token"]
    user = db.scalar(select(User).where(User.username == "disabled"))
    assert user is not None
    user.status = UserStatus.DISABLED
    db.commit()

    response = client.get("/api/v1/auth/me", headers=auth_headers(token))
    assert response.status_code == 403


def _admin(client, db, username: str) -> tuple[str, str]:
    token = register_and_login(client, username)["access_token"]
    admin = _promote(db, username)
    return token, str(admin.id)


def test_admin_can_create_user(client, db):
    token, _ = _admin(client, db, "creator")
    headers = auth_headers(token)

    response = client.post(
        "/api/v1/admin/users",
        json={"username": "fresh", "password": "initial123", "email": "fresh@example.com"},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    assert response.json()["username"] == "fresh"
    assert response.json()["role"] == UserRole.USER

    login = client.post("/api/v1/auth/login", json={"username": "fresh", "password": "initial123"})
    assert login.status_code == 200

    logs = client.get("/api/v1/admin/logs?page_size=100", headers=headers).json()
    assert any(item["action"] == AuditAction.ADMIN_CREATE_USER for item in logs["items"])


def test_admin_create_user_conflicts(client, db):
    token, _ = _admin(client, db, "conflictroot")
    headers = auth_headers(token)
    register_and_login(client, "taken")

    username = client.post(
        "/api/v1/admin/users",
        json={"username": "taken", "password": "initial123"},
        headers=headers,
    )
    assert username.status_code == 409

    email = client.post(
        "/api/v1/admin/users",
        json={"username": "newmail", "password": "initial123", "email": "dup@example.com"},
        headers=headers,
    )
    assert email.status_code == 201
    email_again = client.post(
        "/api/v1/admin/users",
        json={"username": "newmail2", "password": "initial123", "email": "dup@example.com"},
        headers=headers,
    )
    assert email_again.status_code == 409


def test_admin_create_user_requires_admin(client):
    token = register_and_login(client, "notadmin")["access_token"]
    response = client.post(
        "/api/v1/admin/users",
        json={"username": "sneaky", "password": "initial123"},
        headers=auth_headers(token),
    )
    assert response.status_code == 403


def test_admin_can_reset_password(client, db):
    token, admin_id = _admin(client, db, "resetroot")
    headers = auth_headers(token)
    register_and_login(client, "forgetful")
    member = db.scalar(select(User).where(User.username == "forgetful"))
    assert member is not None

    response = client.patch(
        f"/api/v1/admin/users/{member.id}",
        json={"new_password": "brightnew1"},
        headers=headers,
    )
    assert response.status_code == 200, response.text

    old = client.post("/api/v1/auth/login", json={"username": "forgetful", "password": "secret123"})
    assert old.status_code == 401
    new = client.post(
        "/api/v1/auth/login", json={"username": "forgetful", "password": "brightnew1"}
    )
    assert new.status_code == 200

    # Admin must not reset their own password through this route.
    self_reset = client.patch(
        f"/api/v1/admin/users/{admin_id}",
        json={"new_password": "hijack123"},
        headers=headers,
    )
    assert self_reset.status_code == 400


def test_admin_settings_roundtrip_and_masking(client, db):
    token, _ = _admin(client, db, "settingsroot")
    headers = auth_headers(token)

    response = client.get("/api/v1/admin/settings", headers=headers)
    assert response.status_code == 200
    assert response.json()["allow_registration"] is True
    assert response.json()["smtp_password_set"] is False

    response = client.patch(
        "/api/v1/admin/settings",
        json={
            "smtp_host": "smtp.example.com",
            "smtp_port": 587,
            "smtp_username": "postmaster",
            "smtp_password": "super-secret",
            "smtp_sender": "azmark@example.com",
            "registration_captcha_enabled": True,
            "captcha_provider": "turnstile",
            "turnstile_site_key": "1x00000000000000000000AA",
            "turnstile_secret": "1x0000000000000000000000000000000AA",
        },
        headers=headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["smtp_host"] == "smtp.example.com"
    assert body["smtp_username"] == "postmaster"
    assert body["smtp_password_set"] is True
    assert "smtp_password" not in body and "smtp_password_enc" not in body
    assert body["registration_captcha_enabled"] is True
    assert body["captcha_provider"] == "turnstile"
    assert body["turnstile_site_key"] == "1x00000000000000000000AA"
    assert body["turnstile_secret_set"] is True
    assert "turnstile_secret" not in body and "turnstile_secret_key_enc" not in body

    # Stored ciphertext must not equal plaintext.
    row = db.get(SystemSetting, 1)
    assert row is not None
    assert row.smtp_password_enc
    assert "super-secret" not in row.smtp_password_enc
    assert row.turnstile_secret_key_enc
    assert "1x0000000000000000000000000000000AA" not in row.turnstile_secret_key_enc
    from app.core.security import decrypt_field
    from app.models.system_setting import SMTP_PASSWORD_SALT, TURNSTILE_SECRET_SALT

    assert decrypt_field(TURNSTILE_SECRET_SALT, row.turnstile_secret_key_enc) == (
        "1x0000000000000000000000000000000AA"
    )

    # Omitting the passwords keeps them.
    response = client.patch(
        "/api/v1/admin/settings", json={"smtp_sender": "other@example.com"}, headers=headers
    )
    assert response.status_code == 200
    assert response.json()["smtp_password_set"] is True
    assert response.json()["turnstile_secret_set"] is True
    db.refresh(row)
    assert decrypt_field(SMTP_PASSWORD_SALT, row.smtp_password_enc) == "super-secret"

    # Audit meta stores field names only, never values.
    logs = client.get("/api/v1/admin/logs?page_size=100", headers=headers).json()
    settings_entries = [
        item for item in logs["items"] if item["action"] == AuditAction.ADMIN_UPDATE_SETTINGS
    ]
    assert settings_entries
    for entry in settings_entries:
        raw = str(entry.get("meta"))
        assert "super-secret" not in raw


def test_admin_settings_requires_admin(client):
    token = register_and_login(client, "plainsettings")["access_token"]
    headers = auth_headers(token)
    assert client.get("/api/v1/admin/settings", headers=headers).status_code == 403
    patch = client.patch(
        "/api/v1/admin/settings", json={"allow_registration": True}, headers=headers
    )
    assert patch.status_code == 403


class FakeSMTP:
    """Stands in for smtplib.SMTP so tests never touch a real mail server."""

    sent: list[dict] = []

    def __init__(self, host: str, port: int, timeout: int | None = None) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self.tls = False
        self.credentials = None

    def __enter__(self):
        return self

    def __exit__(self, *args) -> bool:
        return False

    def ehlo(self) -> None:  # noqa: D401
        pass

    def starttls(self) -> None:
        self.tls = True

    def login(self, username: str, password: str) -> None:
        self.credentials = (username, password)

    def send_message(self, message) -> None:
        FakeSMTP.sent.append(
            {
                "host": self.host,
                "port": self.port,
                "tls": self.tls,
                "credentials": self.credentials,
                "from": message["From"],
                "to": message["To"],
                "subject": message["Subject"],
            }
        )


def test_admin_test_email_endpoint(client, db, monkeypatch):
    import smtplib

    FakeSMTP.sent = []
    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)

    token, _ = _admin(client, db, "mailroot")
    headers = auth_headers(token)
    client.patch(
        "/api/v1/admin/settings",
        json={
            "smtp_host": "smtp.example.com",
            "smtp_port": 587,
            "smtp_username": "postmaster",
            "smtp_password": "mail-pass",
            "smtp_sender": "azmark@example.com",
        },
        headers=headers,
    )

    response = client.post(
        "/api/v1/admin/settings/test-email",
        json={"to": "pilot@example.com"},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    assert response.json() == {"ok": True}
    assert len(FakeSMTP.sent) == 1
    sent = FakeSMTP.sent[0]
    assert sent["host"] == "smtp.example.com"
    assert sent["port"] == 587
    assert sent["tls"] is True
    assert sent["credentials"] == ("postmaster", "mail-pass")
    assert sent["to"] == "pilot@example.com"


def test_admin_test_email_reports_smtp_failures(client, db, monkeypatch):
    import smtplib

    class BrokenSMTP(FakeSMTP):
        def send_message(self, message) -> None:
            raise smtplib.SMTPException("connection refused")

    monkeypatch.setattr(smtplib, "SMTP", BrokenSMTP)

    token, _ = _admin(client, db, "failmail")
    headers = auth_headers(token)
    client.patch(
        "/api/v1/admin/settings",
        json={"smtp_host": "smtp.example.com", "smtp_sender": "azmark@example.com"},
        headers=headers,
    )
    response = client.post(
        "/api/v1/admin/settings/test-email", json={"to": "x@example.com"}, headers=headers
    )
    assert response.status_code == 502
    assert "connection refused" in response.json()["detail"]


def test_admin_test_email_requires_smtp_config(client, db):
    token, _ = _admin(client, db, "nosmtp")
    headers = auth_headers(token)
    response = client.post(
        "/api/v1/admin/settings/test-email", json={"to": "x@example.com"}, headers=headers
    )
    assert response.status_code == 502
