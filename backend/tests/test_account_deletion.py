from sqlalchemy import func, select

from app.models.ai_setting import UserAiSetting
from app.models.audit_log import AuditLog
from app.models.provider_setting import ProviderSetting
from app.models.transport_record import TransportRecord
from app.models.trip import Trip
from app.models.user import User, UserRole
from tests.conftest import auth_headers, register_and_login


def test_delete_account_requires_password(client, db):
    token = register_and_login(client, "keepme")["access_token"]
    headers = auth_headers(token)

    response = client.post(
        "/api/v1/auth/me/delete", json={"password": "wrongpass"}, headers=headers
    )
    assert response.status_code == 400

    user = db.scalar(select(User).where(User.username == "keepme"))
    assert user is not None


def test_delete_account_removes_data_and_anonymises_audit(client, db):
    token = register_and_login(client, "gone")["access_token"]
    headers = auth_headers(token)

    flight = client.post(
        "/api/v1/flights",
        json={"origin": "HKG", "destination": "SIN", "service_number": "CX659"},
        headers=headers,
    )
    assert flight.status_code == 201, flight.text

    trip = client.post("/api/v1/trips", json={"name": "Singapore 2026"}, headers=headers)
    assert trip.status_code == 201, trip.text

    assert (
        client.put(
            "/api/v1/settings/ai",
            json={"provider": "openai", "model": "gpt-4o-mini"},
            headers=headers,
        ).status_code
        == 200
    )
    assert (
        client.put(
            "/api/v1/settings/provider-keys/aerodatabox",
            json={"api_key": "test-key"},
            headers=headers,
        ).status_code
        == 200
    )

    user_id = db.scalar(select(User.id).where(User.username == "gone"))
    assert user_id is not None

    response = client.post(
        "/api/v1/auth/me/delete", json={"password": "secret123"}, headers=headers
    )
    assert response.status_code == 204, response.text

    assert db.scalar(select(User).where(User.id == user_id)) is None
    for model in (TransportRecord, Trip, UserAiSetting, ProviderSetting):
        total = db.scalar(select(func.count()).select_from(model))
        assert int(total or 0) == 0, model.__name__

    logs = list(db.scalars(select(AuditLog)))
    assert logs
    assert all(log.user_id is None for log in logs)
    assert any(log.action == "account_delete" for log in logs)


def test_last_admin_cannot_delete_account(client, db):
    token = register_and_login(client, "onlyadmin")["access_token"]
    headers = auth_headers(token)
    user = db.scalar(select(User).where(User.username == "onlyadmin"))
    assert user is not None
    user.role = UserRole.ADMIN
    db.commit()

    response = client.post(
        "/api/v1/auth/me/delete", json={"password": "secret123"}, headers=headers
    )
    assert response.status_code == 409
    assert db.scalar(select(User).where(User.id == user.id)) is not None

    # A second active admin makes deletion possible.
    register_and_login(client, "secondadmin")
    second = db.scalar(select(User).where(User.username == "secondadmin"))
    assert second is not None
    second.role = UserRole.ADMIN
    db.commit()

    response = client.post(
        "/api/v1/auth/me/delete", json={"password": "secret123"}, headers=headers
    )
    assert response.status_code == 204, response.text
