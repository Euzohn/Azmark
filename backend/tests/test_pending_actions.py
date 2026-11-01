"""Approval inbox for agent-proposed writes (spec #69, #85)."""

import json
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.models.pending_action import PendingAction, PendingActionStatus
from app.models.transport_record import TransportRecord
from tests.conftest import auth_headers, register_and_login


def _make_write_token(client, username) -> tuple[str, dict[str, str]]:
    """Register, create a write-scope token, return (secret, session_headers)."""
    headers = auth_headers(register_and_login(client, username)["access_token"])
    created = client.post(
        "/api/v1/tokens", json={"name": "agent", "scope": "write"}, headers=headers
    ).json()
    return created["token"], headers


def _mcp_call(client, secret, name, arguments) -> dict:
    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": name, "arguments": arguments},
    }
    resp = client.post(
        "/api/v1/mcp/",
        json=body,
        headers={
            "Authorization": f"Bearer {secret}",
            "Accept": "application/json, text/event-stream",
        },
    )
    assert resp.status_code == 200, resp.text
    return json.loads(resp.json()["result"]["content"][0]["text"])


def _propose_create(client, secret, record_type="flight", data=None) -> dict:
    payload = {
        "record_type": record_type,
        "data": data
        or {
            "origin": "HKG",
            "destination": "NRT",
            "departure_time": "2026-04-29T01:45:00Z",
            "arrival_time": "2026-04-29T06:10:00Z",
            "carrier": "Cathay Pacific",
            "service_number": "CX524",
        },
    }
    return _mcp_call(client, secret, "create_record", payload)


def test_pat_cannot_list_pending_actions(client):
    secret, _ = _make_write_token(client, "pa_pat_list")
    # A PAT authenticates, but the approval inbox is session-only.
    resp = client.get("/api/v1/pending-actions", headers=auth_headers(secret))
    assert resp.status_code == 403
    assert "browser session" in resp.json()["detail"]


def test_pat_cannot_confirm(client):
    secret, _ = _make_write_token(client, "pa_pat_confirm")
    proposal = _propose_create(client, secret)
    action_id = proposal["pending_action_id"]

    resp = client.post(
        f"/api/v1/pending-actions/{action_id}/confirm",
        json={},
        headers=auth_headers(secret),
    )
    assert resp.status_code == 403


def test_create_proposal_does_not_write_record(client, db):
    secret, _ = _make_write_token(client, "pa_no_write")
    proposal = _propose_create(client, secret)
    assert proposal["status"] == "pending_confirmation"
    assert "pending_action_id" in proposal

    # No transport record was created.
    assert db.scalar(select(TransportRecord)) is None
    # A pending action exists, attributed to the token.
    actions = list(db.scalars(select(PendingAction)))
    assert len(actions) == 1
    assert actions[0].status == PendingActionStatus.PENDING
    assert actions[0].token_name == "agent"


def test_session_confirm_creates_record(client, db):
    secret, headers = _make_write_token(client, "pa_confirm")
    proposal = _propose_create(client, secret)
    action_id = proposal["pending_action_id"]

    resp = client.post(f"/api/v1/pending-actions/{action_id}/confirm", json={}, headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "confirmed"
    assert body["result"]["record_type"] == "flight"

    # The flight actually landed in the database.
    records = list(db.scalars(select(TransportRecord)))
    assert len(records) == 1
    assert records[0].service_number == "CX524"

    # Re-confirming the same action is rejected.
    resp = client.post(f"/api/v1/pending-actions/{action_id}/confirm", json={}, headers=headers)
    assert resp.status_code == 409


def test_reject_leaves_no_record(client, db):
    secret, headers = _make_write_token(client, "pa_reject")
    proposal = _propose_create(client, secret)
    action_id = proposal["pending_action_id"]

    resp = client.post(f"/api/v1/pending-actions/{action_id}/reject", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"
    assert db.scalar(select(TransportRecord)) is None


def test_duplicate_keeps_pending_then_force(client, db):
    secret, headers = _make_write_token(client, "pa_dup")
    # Seed an identical flight directly.
    client.post(
        "/api/v1/flights",
        json={
            "origin": "HKG",
            "destination": "NRT",
            "departure_time": "2026-04-29T01:45:00Z",
            "arrival_time": "2026-04-29T06:10:00Z",
            "carrier": "Cathay Pacific",
            "service_number": "CX524",
        },
        headers=headers,
    )

    proposal = _propose_create(client, secret)
    action_id = proposal["pending_action_id"]

    resp = client.post(f"/api/v1/pending-actions/{action_id}/confirm", json={}, headers=headers)
    assert resp.status_code == 409
    assert resp.json()["detail"]["message"] == "Duplicate record"

    # The action is still pending, so the user can retry with force.
    action = db.scalar(select(PendingAction).where(PendingAction.id == uuid.UUID(action_id)))
    assert action.status == PendingActionStatus.PENDING

    resp = client.post(
        f"/api/v1/pending-actions/{action_id}/confirm", json={"force": True}, headers=headers
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "confirmed"


def test_pending_action_user_isolation(client):
    secret_a, headers_a = _make_write_token(client, "pa_iso_a")
    proposal = _propose_create(client, secret_a)
    action_id = proposal["pending_action_id"]

    headers_b = auth_headers(register_and_login(client, "pa_iso_b")["access_token"])
    assert (
        client.get(f"/api/v1/pending-actions/{action_id}", headers=headers_b).status_code == 404
    )
    assert (
        client.post(
            f"/api/v1/pending-actions/{action_id}/confirm", json={}, headers=headers_b
        ).status_code
        == 404
    )
    # Alice still sees it.
    assert client.get("/api/v1/pending-actions", headers=headers_a).json()["total"] == 1


def test_update_proposal_changes_fields(client, db):
    secret, headers = _make_write_token(client, "pa_update")
    created = client.post(
        "/api/v1/flights",
        json={
            "origin": "HKG",
            "destination": "NRT",
            "departure_time": "2026-04-29T01:45:00Z",
            "arrival_time": "2026-04-29T06:10:00Z",
            "carrier": "Cathay Pacific",
            "service_number": "CX524",
        },
        headers=headers,
    ).json()

    proposal = _mcp_call(
        client,
        secret,
        "update_record",
        {"record_type": "flight", "record_id": created["id"], "data": {"seat": "33C"}},
    )
    action_id = proposal["pending_action_id"]

    resp = client.post(f"/api/v1/pending-actions/{action_id}/confirm", json={}, headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "confirmed"

    record = db.scalar(select(TransportRecord))
    assert record.seat == "33C"


def test_invalid_proposal_returns_errors(client, db):
    secret, _ = _make_write_token(client, "pa_invalid")
    payload = _mcp_call(
        client,
        secret,
        "create_record",
        {"record_type": "flight", "data": {"origin": "HKG"}},  # missing destination
    )
    assert payload["error"] == "invalid proposal"
    assert any(field["field"] == "destination" for field in payload["fields"])
    # No pending action was created for a rejected proposal.
    assert db.scalar(select(PendingAction)) is None


def test_expired_action_cannot_be_confirmed(client, db):
    secret, headers = _make_write_token(client, "pa_expired")
    proposal = _propose_create(client, secret)
    action_id = proposal["pending_action_id"]

    action = db.scalar(select(PendingAction).where(PendingAction.id == uuid.UUID(action_id)))
    action.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    db.commit()

    # Confirming an expired proposal is refused with 409; the row flips to
    # "expired" so the inbox shows why it is gone.
    resp = client.post(f"/api/v1/pending-actions/{action_id}/confirm", json={}, headers=headers)
    assert resp.status_code == 409
    assert "expired" in resp.json()["detail"]

    action = db.scalar(select(PendingAction).where(PendingAction.id == uuid.UUID(action_id)))
    assert action.status == PendingActionStatus.EXPIRED


def test_read_token_cannot_call_write_tools(client):
    headers = auth_headers(register_and_login(client, "pa_readonly")["access_token"])
    secret = client.post(
        "/api/v1/tokens", json={"name": "ro", "scope": "read"}, headers=headers
    ).json()["token"]

    payload = _mcp_call(
        client,
        secret,
        "create_record",
        {"record_type": "flight", "data": {"origin": "HKG", "destination": "NRT"}},
    )
    assert payload["error"].startswith("This access token is read-only")


def test_get_pending_action_status_tool(client):
    secret, headers = _make_write_token(client, "pa_status")
    proposal = _propose_create(client, secret)
    action_id = proposal["pending_action_id"]

    status = _mcp_call(client, secret, "get_pending_action", {"pending_action_id": action_id})
    assert status["status"] == "pending"

    client.post(f"/api/v1/pending-actions/{action_id}/reject", headers=headers)
    status = _mcp_call(client, secret, "get_pending_action", {"pending_action_id": action_id})
    assert status["status"] == "rejected"


def test_audit_trail_attributes_token(client):
    secret, headers = _make_write_token(client, "pa_audit")
    proposal = _propose_create(client, secret)
    action_id = proposal["pending_action_id"]

    client.post(f"/api/v1/pending-actions/{action_id}/confirm", json={}, headers=headers)

    entries = client.get("/api/v1/audit-logs", headers=headers).json()["items"]
    actions = {entry["action"] for entry in entries}
    assert "create_pending_action" in actions
    assert "confirm_pending_action" in actions
    create_entry = next(e for e in entries if e["action"] == "create_pending_action")
    assert create_entry["meta"]["actor"]["name"] == "agent"
    assert create_entry["meta"]["record_type"] == "flight"