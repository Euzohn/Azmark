"""Password-age reminder: admin-configurable threshold, server-computed flag.

The flag must agree across every route returning UserRead (/me, profile edit,
password/username change), reset on any password write, and stay off until an
admin opts in (threshold 0 = disabled).
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.models.audit_log import AuditAction, AuditLog
from app.models.user import User, UserRole, utcnow
from app.services.admin import ensure_admin
from tests.conftest import auth_headers, register_and_login


def _promote(db, username: str) -> User:
    user = db.scalars(select(User).where(User.username == username)).one()
    user.role = UserRole.ADMIN
    db.flush()
    return user


def _admin_headers(client, db, username: str) -> dict[str, str]:
    token = register_and_login(client, username)["access_token"]
    _promote(db, username)
    return auth_headers(token)


def _age_password(db, username: str, days: int) -> User:
    user = db.scalars(select(User).where(User.username == username)).one()
    user.password_changed_at = utcnow() - timedelta(days=days)
    db.flush()
    return user


def _set_threshold(client, headers, days: int):
    return client.patch(
        "/api/v1/admin/settings", json={"password_max_age_days": days}, headers=headers
    )


def test_register_stamps_password_changed_at(client):
    response = client.post(
        "/api/v1/auth/register", json={"username": "pwage1", "password": "secret123"}
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["password_changed_at"] is not None
    assert body["password_change_due"] is False
    changed = datetime.fromisoformat(body["password_changed_at"])
    if changed.tzinfo is None:  # SQLite hands back naive datetimes
        changed = changed.replace(tzinfo=UTC)
    assert (datetime.now(UTC) - changed).total_seconds() < 120


def test_reminder_disabled_by_default(client, db):
    headers = auth_headers(register_and_login(client, "pwage2")["access_token"])
    _age_password(db, "pwage2", 400)
    body = client.get("/api/v1/auth/me", headers=headers).json()
    assert body["password_change_due"] is False


def test_admin_enables_reminder_and_flag_is_consistent(client, db):
    admin = _admin_headers(client, db, "pwageroot")
    headers = auth_headers(register_and_login(client, "pwage3")["access_token"])

    response = _set_threshold(client, admin, 90)
    assert response.status_code == 200, response.text
    assert response.json()["password_max_age_days"] == 90

    # Fresh password: not due. Aged past the threshold: due on /me AND on
    # mutation responses, so the banner never flickers off after a profile edit.
    assert client.get("/api/v1/auth/me", headers=headers).json()["password_change_due"] is False
    _age_password(db, "pwage3", 100)
    assert client.get("/api/v1/auth/me", headers=headers).json()["password_change_due"] is True
    patched = client.patch(
        "/api/v1/auth/me", json={"display_name": "Renamed"}, headers=headers
    ).json()
    assert patched["password_change_due"] is True

    # The settings change is audited by field name (never values, #45/#96);
    # the actor is the admin, so match on the action alone.
    entry = db.scalars(
        select(AuditLog)
        .where(AuditLog.action == AuditAction.ADMIN_UPDATE_SETTINGS)
        .order_by(AuditLog.created_at.desc())
    ).first()
    assert entry is not None
    assert "password_max_age_days" in entry.meta["fields"]


def test_change_password_resets_reminder(client, db):
    admin = _admin_headers(client, db, "pwageroot2")
    headers = auth_headers(register_and_login(client, "pwage4")["access_token"])
    _set_threshold(client, admin, 90)
    _age_password(db, "pwage4", 100)
    assert client.get("/api/v1/auth/me", headers=headers).json()["password_change_due"] is True

    response = client.post(
        "/api/v1/auth/me/password",
        json={"current_password": "secret123", "new_password": "newpass123"},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["password_change_due"] is False
    assert client.get("/api/v1/auth/me", headers=headers).json()["password_change_due"] is False


def test_threshold_zero_disables_again(client, db):
    admin = _admin_headers(client, db, "pwageroot3")
    headers = auth_headers(register_and_login(client, "pwage5")["access_token"])
    _set_threshold(client, admin, 30)
    _age_password(db, "pwage5", 60)
    assert client.get("/api/v1/auth/me", headers=headers).json()["password_change_due"] is True
    _set_threshold(client, admin, 0)
    assert client.get("/api/v1/auth/me", headers=headers).json()["password_change_due"] is False


def test_null_timestamp_falls_back_to_created_at(client, db):
    admin = _admin_headers(client, db, "pwageroot4")
    headers = auth_headers(register_and_login(client, "pwage6")["access_token"])
    _set_threshold(client, admin, 90)
    user = db.scalars(select(User).where(User.username == "pwage6")).one()
    user.password_changed_at = None
    user.created_at = utcnow() - timedelta(days=120)
    db.flush()
    assert client.get("/api/v1/auth/me", headers=headers).json()["password_change_due"] is True


def test_threshold_bounds_enforced(client, db):
    admin = _admin_headers(client, db, "pwageroot5")
    assert _set_threshold(client, admin, -1).status_code == 422
    assert _set_threshold(client, admin, 3651).status_code == 422
    assert _set_threshold(client, admin, 3650).status_code == 200


def test_bootstrap_reset_stamps_password_changed_at(client, db):
    register_and_login(client, "pwage7")
    _age_password(db, "pwage7", 200)
    updated, outcome = ensure_admin(
        db, username="pwage7", password="resetpass123", reset_password=True
    )
    assert outcome == "updated"
    after = updated.password_changed_at
    assert after is not None
    if after.tzinfo is None:  # SQLite hands back naive datetimes
        after = after.replace(tzinfo=UTC)
    assert (datetime.now(UTC) - after).total_seconds() < 120
