from sqlalchemy import select

from app.models.audit_log import AuditLog
from app.services.audit import client_user_agent
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


def audit_row(client, headers, action: str) -> dict:
    """Read back the single `action` row from the user-scoped audit endpoint.

    Going through the API (not the DB) also proves the tracing fields are
    actually serialised and returned, not just written.
    """
    response = client.get("/api/v1/audit-logs?page_size=50", headers=headers)
    assert response.status_code == 200, response.text
    items = [item for item in response.json()["items"] if item["action"] == action]
    assert items, f"expected an audited {action}"
    return items[0]


def test_audit_rows_carry_request_context(client):
    """Every row records *which* request made it (spec #47 tracing)."""
    token = register_and_login(client, "audit_ctx")["access_token"]
    headers = {**auth_headers(token), "X-Request-Id": "trace-test-0001"}

    response = client.post(
        "/api/v1/flights",
        json={"origin": "HKG", "destination": "SIN", "service_number": "CX659"},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    # The correlation id is echoed back and stored on the row it identifies.
    assert response.headers["x-request-id"] == "trace-test-0001"

    entry = audit_row(client, headers, "create_record")
    assert entry["request_id"] == "trace-test-0001"
    # Raw address is stored for traceability, plus its salted hash as a stable key.
    assert entry["ip"] == "testclient"
    assert entry["ip_hash"], "the address is also hashed into ip_hash"
    assert entry["user_agent"], "the client hint is captured for tracing"


def test_forwarded_ip_is_recorded(client):
    """Behind a proxy the X-Forwarded-For client is the address that gets stored."""
    token = register_and_login(client, "audit_fwd")["access_token"]
    headers = {**auth_headers(token), "X-Forwarded-For": "203.0.113.7"}

    client.post(
        "/api/v1/flights",
        json={"origin": "HKG", "destination": "SIN", "service_number": "CX659"},
        headers=headers,
    )

    entry = audit_row(client, headers, "create_record")
    assert entry["ip"] == "203.0.113.7"
    # The hash is of the forwarded address, not the proxy hop.
    assert entry["ip_hash"] != entry["ip"]


def test_client_supplied_request_id_must_be_safe(client):
    """A hostile X-Request-Id is ignored, never stored verbatim (#96)."""
    token = register_and_login(client, "audit_badid")["access_token"]
    headers = {**auth_headers(token), "X-Request-Id": "bad id\r\nX-Evil: yes"}

    response = client.post(
        "/api/v1/flights",
        json={"origin": "HKG", "destination": "SIN", "service_number": "CX659"},
        headers=headers,
    )
    assert response.status_code == 201, response.text

    entry = audit_row(client, headers, "create_record")
    # Rejected: a server-generated id is used instead, with no injected newline.
    assert entry["request_id"]
    assert entry["request_id"] != "bad id\r\nX-Evil: yes"
    assert "\r" not in entry["request_id"] and "\n" not in entry["request_id"]
    # The echoed header is the server-generated id, not the injected one.
    assert response.headers["x-request-id"] == entry["request_id"]


def test_user_agent_is_sanitised_before_storage():
    """Control characters are stripped so UA cannot inject into rows/logs (#96)."""
    from starlette.requests import Request

    raw = "Mozilla/5.0\r\nX-Injected: yes\x00more"
    request = Request(
        {"type": "http", "headers": [(b"user-agent", raw.encode("latin-1"))], "method": "GET"}
    )
    cleaned = client_user_agent(request)
    assert cleaned == "Mozilla/5.0X-Injected: yesmore"
    assert "\r" not in cleaned and "\n" not in cleaned and "\x00" not in cleaned


def test_user_agent_absent_is_none():
    from starlette.requests import Request

    request = Request({"type": "http", "headers": [], "method": "GET"})
    assert client_user_agent(request) is None
