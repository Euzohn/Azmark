"""Tests for DataSource provenance endpoints (spec #22, #37, #57)."""

from sqlalchemy import select

from app.models.user import User
from app.services.data_source import DataSourceService
from tests.conftest import auth_headers, register_and_login


def _user_id(db, username: str):
    user = db.scalar(select(User).where(User.username == username))
    assert user is not None
    return user.id


def test_data_source_list_metadata_and_delete(client, db):
    token = register_and_login(client, "ds_owner")["access_token"]
    headers = auth_headers(token)
    source = DataSourceService(db).record(
        user_id=_user_id(db, "ds_owner"),
        source_type="api",
        source_name="CX659 · 2026-09-26",
        source_url="https://aerodatabox.com",
        provider="aerodatabox",
        confidence=0.9,
        metadata={"flight_number": "CX659", "origin": "HKG"},
    )

    response = client.get("/api/v1/data-sources", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["source_type"] == "api"
    assert body["items"][0]["provider"] == "aerodatabox"
    assert body["items"][0]["metadata"] == {"flight_number": "CX659", "origin": "HKG"}
    assert "meta" not in body["items"][0]

    detail = client.get(f"/api/v1/data-sources/{source.id}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["source_name"] == "CX659 · 2026-09-26"

    assert client.delete(f"/api/v1/data-sources/{source.id}", headers=headers).status_code == 204
    assert client.get("/api/v1/data-sources", headers=headers).json()["total"] == 0


def test_data_source_is_user_scoped(client, db):
    owner = register_and_login(client, "ds_a")["access_token"]
    other = register_and_login(client, "ds_b")["access_token"]
    source = DataSourceService(db).record(
        user_id=_user_id(db, "ds_a"),
        source_type="import",
        source_name="trips.csv",
        provider="csv",
        confidence=1.0,
        metadata={"imported": 3},
    )

    assert client.get("/api/v1/data-sources", headers=auth_headers(owner)).json()["total"] == 1
    assert client.get("/api/v1/data-sources", headers=auth_headers(other)).json()["total"] == 0
    assert (
        client.get(f"/api/v1/data-sources/{source.id}", headers=auth_headers(other)).status_code
        == 404
    )
    assert (
        client.delete(f"/api/v1/data-sources/{source.id}", headers=auth_headers(other)).status_code
        == 404
    )
    # The owner can still delete it after the failed cross-user attempt.
    assert (
        client.delete(f"/api/v1/data-sources/{source.id}", headers=auth_headers(owner)).status_code
        == 204
    )
