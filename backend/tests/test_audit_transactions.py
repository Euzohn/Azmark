"""Database writes and their audit record must succeed or roll back together."""

import json

import pytest
from sqlalchemy import select

from app.models.activity import Activity
from app.models.idempotency_key import IdempotencyKey
from app.models.pending_action import PendingAction
from app.services.activity import ActivityService
from app.services.audit import AuditService
from tests.conftest import auth_headers, register_and_login
from tests.test_pending_actions import _make_write_token, _propose


def _fail_audit(*args, **kwargs):
    raise RuntimeError("simulated audit failure")


def _failed_request(db, monkeypatch, call):
    with monkeypatch.context() as patch:
        patch.setattr(AuditService, "log", _fail_audit)
        with pytest.raises(RuntimeError, match="simulated audit failure"):
            call()
        # Production get_db closes the failed request's session. The test
        # fixture shares one session across requests, so emulate that rollback.
        db.rollback()


def test_activity_and_idempotency_rollback_then_retry(client, db, monkeypatch):
    headers = auth_headers(register_and_login(client, "audit_activity")["access_token"])
    trip = client.post("/api/v1/trips", json={"name": "Trip"}, headers=headers).json()
    headers["Idempotency-Key"] = "retry-activity"
    payload = {"name": "Visit", "trip_id": trip["id"]}
    _failed_request(
        db, monkeypatch, lambda: client.post("/api/v1/activities", json=payload, headers=headers)
    )
    assert client.get(f"/api/v1/trips/{trip['id']}", headers=headers).json()["items"] == []
    response = client.post("/api/v1/activities", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    assert len(client.get(f"/api/v1/trips/{trip['id']}", headers=headers).json()["items"]) == 1


def test_source_delete_and_attachment_rollback(client, db, storage, monkeypatch):
    headers = auth_headers(register_and_login(client, "audit_delete")["access_token"])
    trip = client.post("/api/v1/trips", json={"name": "Trip"}, headers=headers).json()
    flight = client.post(
        "/api/v1/flights",
        json={"origin": "HKG", "destination": "NRT", "trip_id": trip["id"]},
        headers=headers,
    ).json()
    expense = client.post(
        "/api/v1/expenses",
        json={
            "category": "transport",
            "amount": "100",
            "currency": "SGD",
            "source_type": "transport",
            "source_id": flight["id"],
        },
        headers=headers,
    ).json()
    upload = client.post(
        "/api/v1/attachments",
        data={"resource_type": "flight", "resource_id": flight["id"]},
        files={"file": ("test.pdf", b"%PDF-1.4 test", "application/pdf")},
        headers=headers,
    )
    assert upload.status_code == 201
    objects = dict(storage.objects)
    _failed_request(
        db, monkeypatch, lambda: client.delete(f"/api/v1/flights/{flight['id']}", headers=headers)
    )
    assert client.get(f"/api/v1/flights/{flight['id']}", headers=headers).status_code == 200
    assert (
        client.get(f"/api/v1/expenses/{expense['id']}", headers=headers).json()["source_id"]
        == flight["id"]
    )
    assert len(client.get(f"/api/v1/trips/{trip['id']}", headers=headers).json()["items"]) == 1
    assert (
        client.get(
            f"/api/v1/attachments/{upload.json()['id']}/download", headers=headers
        ).status_code
        == 200
    )
    assert storage.objects == objects


def test_trip_delete_and_expense_update_rollback(client, db, monkeypatch):
    headers = auth_headers(register_and_login(client, "audit_trip")["access_token"])
    trip = client.post("/api/v1/trips", json={"name": "Trip"}, headers=headers).json()
    expense = client.post(
        "/api/v1/expenses",
        json={"category": "other", "amount": "10", "currency": "USD", "trip_id": trip["id"]},
        headers=headers,
    ).json()
    _failed_request(
        db,
        monkeypatch,
        lambda: client.patch(
            f"/api/v1/expenses/{expense['id']}", json={"amount": "20"}, headers=headers
        ),
    )
    assert (
        float(client.get(f"/api/v1/expenses/{expense['id']}", headers=headers).json()["amount"])
        == 10
    )
    _failed_request(
        db, monkeypatch, lambda: client.delete(f"/api/v1/trips/{trip['id']}", headers=headers)
    )
    assert client.get(f"/api/v1/trips/{trip['id']}", headers=headers).status_code == 200
    assert (
        client.get(f"/api/v1/expenses/{expense['id']}", headers=headers).json()["trip_id"]
        == trip["id"]
    )


def test_pending_confirmation_audit_failure_can_retry(client, db, monkeypatch):
    secret, headers = _make_write_token(client, "audit_pending")
    action_id = _propose(client, secret, "activity", {"name": "Visit"})["pending_action_id"]
    _failed_request(
        db,
        monkeypatch,
        lambda: client.post(
            f"/api/v1/pending-actions/{action_id}/confirm", json={}, headers=headers
        ),
    )
    assert db.scalar(select(Activity)) is None
    assert db.scalar(select(IdempotencyKey)) is None
    assert db.scalar(select(PendingAction)).status == "pending"
    assert (
        client.post(
            f"/api/v1/pending-actions/{action_id}/confirm", json={}, headers=headers
        ).status_code
        == 200
    )
    assert len(list(db.scalars(select(Activity)))) == 1


def test_pending_execution_error_discards_flushed_business_rows(client, db, monkeypatch):
    secret, headers = _make_write_token(client, "pending_partial_error")
    action_id = _propose(client, secret, "activity", {"name": "Visit"})["pending_action_id"]
    original = ActivityService.create_activity_idempotent

    def fail_after_write(self, **kwargs):
        original(self, **kwargs)
        raise ValueError("simulated execution failure")

    monkeypatch.setattr(ActivityService, "create_activity_idempotent", fail_after_write)
    response = client.post(f"/api/v1/pending-actions/{action_id}/confirm", json={}, headers=headers)
    assert response.status_code == 400
    assert db.scalar(select(Activity)) is None
    assert db.scalar(select(IdempotencyKey)) is None
    assert db.scalar(select(PendingAction)).status == "failed"


def test_v2_import_audit_failure_can_retry(client, db, monkeypatch):
    source = auth_headers(register_and_login(client, "audit_export")["access_token"])
    target = auth_headers(register_and_login(client, "audit_import")["access_token"])
    trip = client.post("/api/v1/trips", json={"name": "Imported"}, headers=source).json()
    assert (
        client.post(
            "/api/v1/activities", json={"name": "Visit", "trip_id": trip["id"]}, headers=source
        ).status_code
        == 201
    )
    bundle = json.dumps(client.get("/api/v1/export?format=json", headers=source).json())

    def do_import():
        return client.post(
            "/api/v1/import",
            files={"file": ("bundle.json", bundle, "application/json")},
            data={"format": "json"},
            headers=target,
        )

    _failed_request(db, monkeypatch, do_import)
    assert client.get("/api/v1/trips", headers=target).json()["total"] == 0
    response = do_import()
    assert response.status_code == 200, response.text
    assert client.get("/api/v1/trips", headers=target).json()["total"] == 1
