from sqlalchemy import select

from app.models.audit_log import AuditLog
from tests.conftest import auth_headers, register_and_login


def _actions(client, headers):
    response = client.get("/api/v1/audit-logs", headers=headers)
    assert response.status_code == 200, response.text
    return [item["action"] for item in response.json()["items"]]


def test_login_and_record_actions_are_audited(client):
    token = register_and_login(client, "audited")["access_token"]
    headers = auth_headers(token)

    client.post(
        "/api/v1/flights",
        json={"origin": "HKG", "destination": "SIN", "service_number": "CX659"},
        headers=headers,
    )

    actions = _actions(client, headers)
    assert "register" in actions
    assert "login" in actions
    assert "create_record" in actions


def test_update_and_delete_are_audited(client):
    token = register_and_login(client, "audited2")["access_token"]
    headers = auth_headers(token)

    created = client.post(
        "/api/v1/flights",
        json={"origin": "HKG", "destination": "SIN", "service_number": "CX659"},
        headers=headers,
    ).json()
    client.patch(f"/api/v1/flights/{created['id']}", json={"seat": "33C"}, headers=headers)
    client.delete(f"/api/v1/flights/{created['id']}", headers=headers)

    actions = _actions(client, headers)
    assert "update_record" in actions
    assert "delete_record" in actions


def test_password_change_is_audited(client):
    token = register_and_login(client, "audited3")["access_token"]
    headers = auth_headers(token)
    client.post(
        "/api/v1/auth/me/password",
        json={"current_password": "secret123", "new_password": "newpass123"},
        headers=headers,
    )
    assert "password_change" in _actions(client, headers)


def test_failed_login_is_audited_without_user(client, db):
    token = register_and_login(client, "audited4")["access_token"]
    headers = auth_headers(token)

    response = client.post("/api/v1/auth/login", json={"username": "audited4", "password": "wrong"})
    assert response.status_code == 401

    entry = db.scalar(select(AuditLog).where(AuditLog.action == "login_failed"))
    assert entry is not None
    assert entry.user_id is None

    # Failed logins are not exposed through the user-scoped audit endpoint.
    assert "login_failed" not in _actions(client, headers)


def test_audit_logs_are_user_scoped(client):
    token_a = register_and_login(client, "audit_a")["access_token"]
    token_b = register_and_login(client, "audit_b")["access_token"]

    client.post(
        "/api/v1/flights",
        json={"origin": "HKG", "destination": "SIN"},
        headers=auth_headers(token_a),
    )

    actions_b = _actions(client, auth_headers(token_b))
    assert "create_record" not in actions_b


def test_audit_does_not_store_sensitive_values(client):
    token = register_and_login(client, "audited5")["access_token"]
    headers = auth_headers(token)
    client.post(
        "/api/v1/flights",
        json={
            "origin": "HKG",
            "destination": "SIN",
            "booking_reference": "ABC123",
            "ticket_number": "1234567890",
        },
        headers=headers,
    )

    response = client.get("/api/v1/audit-logs", headers=headers)
    payload = response.text
    assert "ABC123" not in payload
    assert "1234567890" not in payload
