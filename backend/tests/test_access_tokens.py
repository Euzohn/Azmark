import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.api import deps
from app.models.audit_log import AuditLog
from app.models.personal_access_token import PersonalAccessToken
from tests.conftest import auth_headers, register_and_login


def _create_token(client, headers, **overrides):
    payload = {"name": "Claude Desktop", "scope": "read", **overrides}
    response = client.post("/api/v1/tokens", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def test_create_token_returns_secret_once(client):
    headers = auth_headers(register_and_login(client, "token_create")["access_token"])
    created = _create_token(client, headers, scope="read")

    assert created["token"].startswith("azm_")
    assert created["token_prefix"] == created["token"][:12]
    assert created["scope"] == "read"
    assert created["revoked_at"] is None
    assert created["last_used_at"] is None
    assert created["expires_at"] is not None

    listed = client.get("/api/v1/tokens", headers=headers)
    assert listed.status_code == 200
    item = listed.json()["items"][0]
    assert "token" not in item
    assert "token_hash" not in item


def test_non_expiring_token(client):
    headers = auth_headers(register_and_login(client, "token_forever")["access_token"])
    created = _create_token(client, headers, expires_in_days=None)
    assert created["expires_at"] is None


def test_pat_authenticates_as_owner(client):
    headers = auth_headers(register_and_login(client, "token_auth")["access_token"])
    secret = _create_token(client, headers)["token"]

    response = client.get("/api/v1/auth/me", headers=auth_headers(secret))
    assert response.status_code == 200
    assert response.json()["username"] == "token_auth"


def test_read_token_cannot_mutate(client):
    headers = auth_headers(register_and_login(client, "token_readonly")["access_token"])
    secret = _create_token(client, headers, scope="read")["token"]

    response = client.post("/api/v1/trips", json={"name": "Nope"}, headers=auth_headers(secret))
    assert response.status_code == 403
    assert "read-only" in response.json()["detail"]

    # Creating another token is a write too.
    response = client.post("/api/v1/tokens", json={"name": "nested"}, headers=auth_headers(secret))
    assert response.status_code == 403


def test_write_token_can_mutate(client):
    headers = auth_headers(register_and_login(client, "token_write")["access_token"])
    secret = _create_token(client, headers, scope="write")["token"]

    response = client.post("/api/v1/trips", json={"name": "Osaka"}, headers=auth_headers(secret))
    assert response.status_code == 201, response.text


def test_revoked_token_is_rejected(client):
    headers = auth_headers(register_and_login(client, "token_revoke")["access_token"])
    created = _create_token(client, headers)

    response = client.post(f"/api/v1/tokens/{created['id']}/revoke", headers=headers)
    assert response.status_code == 204

    response = client.get("/api/v1/auth/me", headers=auth_headers(created["token"]))
    assert response.status_code == 401

    listed = client.get("/api/v1/tokens", headers=headers).json()["items"][0]
    assert listed["revoked_at"] is not None


def test_deleted_token_is_rejected(client):
    headers = auth_headers(register_and_login(client, "token_delete")["access_token"])
    created = _create_token(client, headers)

    response = client.delete(f"/api/v1/tokens/{created['id']}", headers=headers)
    assert response.status_code == 204

    response = client.get("/api/v1/auth/me", headers=auth_headers(created["token"]))
    assert response.status_code == 401
    assert client.get("/api/v1/tokens", headers=headers).json()["items"] == []


def test_expired_token_is_rejected(client, db):
    headers = auth_headers(register_and_login(client, "token_expired")["access_token"])
    created = _create_token(client, headers)

    record = db.scalar(
        select(PersonalAccessToken).where(PersonalAccessToken.id == uuid.UUID(created["id"]))
    )
    record.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    db.commit()

    response = client.get("/api/v1/auth/me", headers=auth_headers(created["token"]))
    assert response.status_code == 401


def test_token_is_invisible_to_other_users(client):
    alice = auth_headers(register_and_login(client, "token_alice")["access_token"])
    bob = auth_headers(register_and_login(client, "token_bob")["access_token"])
    created = _create_token(client, alice, scope="write")

    assert client.get("/api/v1/tokens", headers=bob).json()["items"] == []
    assert client.post(f"/api/v1/tokens/{created['id']}/revoke", headers=bob).status_code == 404
    assert client.delete(f"/api/v1/tokens/{created['id']}", headers=bob).status_code == 404

    # And Alice's token stays usable.
    response = client.post(
        "/api/v1/trips", json={"name": "Mine"}, headers=auth_headers(created["token"])
    )
    assert response.status_code == 201


def test_token_cannot_read_another_users_records(client):
    alice = auth_headers(register_and_login(client, "token_iso_a")["access_token"])
    secret = _create_token(client, alice, scope="write")["token"]
    client.post("/api/v1/trips", json={"name": "Alice trip"}, headers=auth_headers(secret))

    bob_headers = auth_headers(register_and_login(client, "token_iso_b")["access_token"])
    bob_secret = _create_token(client, bob_headers)["token"]
    response = client.get("/api/v1/trips", headers=auth_headers(bob_secret))
    assert response.status_code == 200
    assert response.json()["items"] == []


def test_invalid_token_is_rejected(client):
    response = client.get("/api/v1/auth/me", headers=auth_headers("azm_not-a-real-token"))
    assert response.status_code == 401
    assert client.get("/api/v1/auth/me", headers=auth_headers("garbage")).status_code == 401


def test_last_used_at_is_tracked(client):
    headers = auth_headers(register_and_login(client, "token_used")["access_token"])
    created = _create_token(client, headers)

    assert client.get("/api/v1/auth/me", headers=auth_headers(created["token"])).status_code == 200

    listed = client.get("/api/v1/tokens", headers=headers).json()["items"][0]
    assert listed["last_used_at"] is not None


def test_audit_trail_attributes_the_token(client):
    headers = auth_headers(register_and_login(client, "token_audit")["access_token"])
    created = _create_token(client, headers, scope="write")

    client.post("/api/v1/trips", json={"name": "Audited"}, headers=auth_headers(created["token"]))

    entries = client.get("/api/v1/audit-logs", headers=headers).json()["items"]
    trip_entry = next(entry for entry in entries if entry["action"] == "create_record")
    assert trip_entry["meta"]["actor"] == {
        "kind": "access_token",
        "id": created["id"],
        "name": created["name"],
    }
    assert created["token"] not in str(trip_entry["meta"])


def test_token_secret_is_never_persisted_in_plaintext(client, db):
    headers = auth_headers(register_and_login(client, "token_storage")["access_token"])
    created = _create_token(client, headers)

    record = db.scalar(
        select(PersonalAccessToken).where(PersonalAccessToken.id == uuid.UUID(created["id"]))
    )
    assert record.token_hash != created["token"]
    assert len(record.token_hash) == 64
    assert record.token_prefix == created["token"][:12]

    audits = db.scalars(select(AuditLog)).all()
    assert all(created["token"] not in str(entry.meta) for entry in audits)


def test_rate_limit_returns_429(client):
    headers = auth_headers(register_and_login(client, "token_ratelimit")["access_token"])
    created = _create_token(client, headers)

    original = deps.access_token_limiter.limit
    deps.access_token_limiter.reset()
    deps.access_token_limiter.limit = 2
    try:
        me = "/api/v1/auth/me"
        assert client.get(me, headers=auth_headers(created["token"])).status_code == 200
        assert client.get(me, headers=auth_headers(created["token"])).status_code == 200
        response = client.get(me, headers=auth_headers(created["token"]))
        assert response.status_code == 429
        assert response.headers["retry-after"] == "60"
    finally:
        deps.access_token_limiter.limit = original
        deps.access_token_limiter.reset()


def test_blank_name_is_rejected(client):
    headers = auth_headers(register_and_login(client, "token_blank")["access_token"])
    response = client.post("/api/v1/tokens", json={"name": "   "}, headers=headers)
    assert response.status_code == 422


def test_unknown_scope_is_rejected(client):
    headers = auth_headers(register_and_login(client, "token_scope")["access_token"])
    response = client.post(
        "/api/v1/tokens", json={"name": "bad", "scope": "admin"}, headers=headers
    )
    assert response.status_code == 422
