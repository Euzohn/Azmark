"""Hotel CRUD, dedup and trip integration (spec #17, #41, #57)."""

import uuid
from datetime import date, timedelta

from sqlalchemy import select

from app.models.hotel import Hotel
from app.models.trip_item import TripItem
from tests.conftest import auth_headers, register_and_login

HOTEL = {
    "hotel": "Marina Bay Sands",
    "check_in": "2026-04-29",
    "check_out": "2026-05-02",
    "room_type": "Deluxe King",
    "room_number": "1208",
    "address": "10 Bayfront Ave, Singapore",
    "price": "420.00",
    "currency": "SGD",
    "booking_reference": "MBS-778812",
}


def _headers(client, username: str) -> dict[str, str]:
    return auth_headers(register_and_login(client, username)["access_token"])


def test_create_and_read_hotel(client):
    headers = _headers(client, "hotel_create")
    resp = client.post("/api/v1/hotels", json=HOTEL, headers=headers)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["hotel"] == "Marina Bay Sands"
    assert body["booking_reference"] == "MBS-778812"

    got = client.get(f"/api/v1/hotels/{body['id']}", headers=headers)
    assert got.status_code == 200
    assert got.json()["room_number"] == "1208"


def test_booking_reference_encrypted_at_rest(client, db):
    headers = _headers(client, "hotel_enc")
    created = client.post("/api/v1/hotels", json=HOTEL, headers=headers).json()
    row = db.scalar(select(Hotel).where(Hotel.id == uuid.UUID(created["id"])))
    assert row.booking_reference_enc
    assert "MBS-778812" not in row.booking_reference_enc
    assert row.booking_reference == "MBS-778812"


def test_list_and_search(client):
    headers = _headers(client, "hotel_list")
    client.post("/api/v1/hotels", json=HOTEL, headers=headers)
    client.post(
        "/api/v1/hotels",
        json={
            **HOTEL,
            "hotel": "Park Hyatt Tokyo",
            "check_in": "2026-06-01",
            "check_out": "2026-06-03",
            "booking_reference": None,
        },
        headers=headers,
    )
    assert client.get("/api/v1/hotels", headers=headers).json()["total"] == 2
    found = client.get("/api/v1/hotels", params={"search": "hyatt"}, headers=headers).json()
    assert found["total"] == 1
    assert found["items"][0]["hotel"] == "Park Hyatt Tokyo"


def test_update_hotel(client):
    headers = _headers(client, "hotel_update")
    created = client.post("/api/v1/hotels", json=HOTEL, headers=headers).json()
    resp = client.patch(
        f"/api/v1/hotels/{created['id']}",
        json={"room_number": "1500", "status": "cancelled"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["room_number"] == "1500"
    assert resp.json()["status"] == "cancelled"


def test_delete_hotel(client, db):
    headers = _headers(client, "hotel_delete")
    created = client.post("/api/v1/hotels", json=HOTEL, headers=headers).json()
    assert client.delete(f"/api/v1/hotels/{created['id']}", headers=headers).status_code == 204
    assert client.get(f"/api/v1/hotels/{created['id']}", headers=headers).status_code == 404
    assert db.scalar(select(Hotel)) is None


def test_duplicate_then_force(client):
    headers = _headers(client, "hotel_dup")
    first = client.post("/api/v1/hotels", json=HOTEL, headers=headers)
    assert first.status_code == 201
    dup = client.post("/api/v1/hotels", json=HOTEL, headers=headers)
    assert dup.status_code == 409
    assert dup.json()["detail"]["existing_record"]["id"] == first.json()["id"]
    forced = client.post("/api/v1/hotels", params={"force": "true"}, json=HOTEL, headers=headers)
    assert forced.status_code == 201


def test_user_isolation(client):
    a = _headers(client, "hotel_iso_a")
    b = _headers(client, "hotel_iso_b")
    created = client.post("/api/v1/hotels", json=HOTEL, headers=a).json()
    assert client.get(f"/api/v1/hotels/{created['id']}", headers=b).status_code == 404
    assert (
        client.patch(f"/api/v1/hotels/{created['id']}", json={"notes": "x"}, headers=b).status_code
        == 404
    )
    assert client.delete(f"/api/v1/hotels/{created['id']}", headers=b).status_code == 404
    assert client.get("/api/v1/hotels", headers=b).json()["total"] == 0


def test_invalid_dates_rejected(client):
    headers = _headers(client, "hotel_dates")
    resp = client.post(
        "/api/v1/hotels",
        json={**HOTEL, "check_in": "2026-05-02", "check_out": "2026-04-29"},
        headers=headers,
    )
    assert resp.status_code == 422


def test_trip_assignment_and_item_sync(client, db):
    headers = _headers(client, "hotel_trip")
    trip = client.post("/api/v1/trips", json={"name": "Singapore 2026"}, headers=headers).json()
    created = client.post("/api/v1/hotels", json={**HOTEL, "trip_id": trip["id"]}, headers=headers)
    assert created.status_code == 201, created.text
    hotel_id = created.json()["id"]

    detail = client.get(f"/api/v1/trips/{trip['id']}", headers=headers).json()
    hotel_items = [i for i in detail["items"] if i["item_type"] == "hotel"]
    assert len(hotel_items) == 1
    assert hotel_items[0]["hotel"]["id"] == hotel_id

    client.patch(f"/api/v1/hotels/{hotel_id}", json={"trip_id": None}, headers=headers)
    assert db.scalar(select(TripItem).where(TripItem.item_type == "hotel")) is None


def test_trip_from_another_user_rejected(client):
    a = _headers(client, "hotel_trip_a")
    b = _headers(client, "hotel_trip_b")
    trip = client.post("/api/v1/trips", json={"name": "Alice trip"}, headers=a).json()
    assert (
        client.post("/api/v1/hotels", json={**HOTEL, "trip_id": trip["id"]}, headers=b).status_code
        == 404
    )


def test_read_token_cannot_create(client):
    headers = _headers(client, "hotel_readtoken")
    secret = client.post(
        "/api/v1/tokens", json={"name": "ro", "scope": "read"}, headers=headers
    ).json()["token"]
    assert (
        client.post("/api/v1/hotels", json=HOTEL, headers=auth_headers(secret)).status_code == 403
    )


def test_status_inferred_from_dates(client):
    headers = _headers(client, "hotel_status")
    past_in = (date.today() - timedelta(days=10)).isoformat()
    past_out = (date.today() - timedelta(days=7)).isoformat()
    past = client.post(
        "/api/v1/hotels",
        json={"hotel": "Past Stay", "check_in": past_in, "check_out": past_out},
        headers=headers,
    )
    assert past.json()["status"] == "completed"
    upcoming = (date.today() + timedelta(days=10)).isoformat()
    future = client.post(
        "/api/v1/hotels",
        json={"hotel": "Future Stay", "check_in": upcoming},
        headers=headers,
    )
    assert future.json()["status"] == "scheduled"


def test_audit_log(client):
    headers = _headers(client, "hotel_audit")
    created = client.post("/api/v1/hotels", json=HOTEL, headers=headers).json()
    client.delete(f"/api/v1/hotels/{created['id']}", headers=headers)
    entries = client.get("/api/v1/audit-logs", headers=headers).json()["items"]
    hotel_actions = {e["action"] for e in entries if e["resource_type"] == "hotel"}
    assert "create_record" in hotel_actions
    assert "delete_record" in hotel_actions


def test_hotel_coordinates_roundtrip(client):
    headers = _headers(client, "hotel_coords")
    resp = client.post(
        "/api/v1/hotels",
        json={**HOTEL, "lat": 1.2834, "lon": 103.8607},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["lat"] == 1.2834
    assert body["lon"] == 103.8607

    got = client.get(f"/api/v1/hotels/{body['id']}", headers=headers).json()
    assert got["lat"] == 1.2834
    assert got["lon"] == 103.8607

    # out-of-range coordinates are rejected
    bad = client.post(
        "/api/v1/hotels", json={**HOTEL, "hotel": "Other", "lat": 95.0}, headers=headers
    )
    assert bad.status_code == 422


def test_geocode_hotel_stores_coordinates(client, monkeypatch):
    headers = _headers(client, "hotel_geocode")
    created = client.post("/api/v1/hotels", json=HOTEL, headers=headers).json()
    assert created["lat"] is None

    from app.providers.geocode import GeocodeProvider, GeocodeResult

    async def fake_search(self, query, *, limit=1):
        assert query == HOTEL["address"]
        return GeocodeResult(lat=1.2834, lon=103.8607, display_name="Marina Bay Sands")

    monkeypatch.setattr(GeocodeProvider, "search", fake_search)

    resp = client.post(f"/api/v1/hotels/{created['id']}/geocode", headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["lat"] == 1.2834
    assert resp.json()["lon"] == 103.8607


def test_geocode_hotel_without_result_returns_404(client, monkeypatch):
    headers = _headers(client, "hotel_geocode_none")
    created = client.post("/api/v1/hotels", json=HOTEL, headers=headers).json()

    from app.providers.geocode import GeocodeProvider

    async def fake_search(self, query, *, limit=1):
        return None

    monkeypatch.setattr(GeocodeProvider, "search", fake_search)
    resp = client.post(f"/api/v1/hotels/{created['id']}/geocode", headers=headers)
    assert resp.status_code == 404


def test_geocode_hotel_is_user_scoped(client, monkeypatch):
    headers_a = _headers(client, "hotel_geo_a")
    headers_b = _headers(client, "hotel_geo_b")
    created = client.post("/api/v1/hotels", json=HOTEL, headers=headers_a).json()

    from app.providers.geocode import GeocodeProvider, GeocodeResult

    async def fake_search(self, query, *, limit=1):
        return GeocodeResult(lat=0.0, lon=0.0)

    monkeypatch.setattr(GeocodeProvider, "search", fake_search)
    resp = client.post(f"/api/v1/hotels/{created['id']}/geocode", headers=headers_b)
    assert resp.status_code == 404
