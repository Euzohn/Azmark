from sqlalchemy import select

from app.core.security import verify_password
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
