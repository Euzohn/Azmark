import uuid

from tests.conftest import auth_headers, register_and_login

TRANSPORT = {
    "origin": "上海",
    "destination": "舟山",
    "departure_time": "2026-09-27T09:00:00Z",
    "arrival_time": "2026-09-27T13:30:00Z",
    "carrier": "舟山轮渡",
    "service_number": "FERRY-12",
    "vehicle_type": "ferry",
    "seat": "B12",
    "price": "120.00",
    "currency": "CNY",
}


def test_create_and_list_transport(client):
    token = register_and_login(client, "transporter")["access_token"]
    headers = auth_headers(token)

    response = client.post("/api/v1/other-transports", json=TRANSPORT, headers=headers)
    assert response.status_code == 201, response.text
    created = response.json()
    assert created["type"] == "other"
    assert created["service_number"] == "FERRY-12"
    assert created["vehicle_type"] == "ferry"

    response = client.get("/api/v1/other-transports", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == created["id"]


def test_transport_crud_and_search(client):
    token = register_and_login(client, "transport_crud")["access_token"]
    headers = auth_headers(token)

    created = client.post("/api/v1/other-transports", json=TRANSPORT, headers=headers).json()

    response = client.get("/api/v1/other-transports", params={"search": "轮渡"}, headers=headers)
    assert response.json()["total"] == 1

    response = client.get("/api/v1/other-transports", params={"search": "NOPE"}, headers=headers)
    assert response.json()["total"] == 0

    response = client.patch(
        f"/api/v1/other-transports/{created['id']}", json={"seat": "C01"}, headers=headers
    )
    assert response.status_code == 200
    assert response.json()["seat"] == "C01"
    assert response.json()["vehicle_type"] == "ferry"

    response = client.delete(f"/api/v1/other-transports/{created['id']}", headers=headers)
    assert response.status_code == 204
    assert (
        client.get(f"/api/v1/other-transports/{created['id']}", headers=headers).status_code == 404
    )


def test_transport_sensitive_encrypted_at_rest(client, db):
    from sqlalchemy import select

    from app.core.crypto import decrypt_value
    from app.models.transport_record import TransportRecord

    token = register_and_login(client, "transport_cred")["access_token"]
    headers = auth_headers(token)

    payload = {**TRANSPORT, "ticket_number": "T123456789", "booking_reference": "REF123"}
    created = client.post("/api/v1/other-transports", json=payload, headers=headers).json()
    assert created["ticket_number"] == "T123456789"
    assert created["booking_reference"] == "REF123"

    row = db.scalar(select(TransportRecord).where(TransportRecord.id == uuid.UUID(created["id"])))
    assert row is not None
    assert row.type == "other"
    for enc, plain in (("ticket_number_enc", "T123456789"), ("booking_reference_enc", "REF123")):
        assert getattr(row, enc) != plain
        assert decrypt_value(getattr(row, enc)) == plain


def test_transport_user_isolation(client):
    token_a = register_and_login(client, "transport_a")["access_token"]
    token_b = register_and_login(client, "transport_b")["access_token"]

    created = client.post(
        "/api/v1/other-transports", json=TRANSPORT, headers=auth_headers(token_a)
    ).json()
    record_id = created["id"]

    assert (
        client.get("/api/v1/other-transports", headers=auth_headers(token_b)).json()["total"] == 0
    )
    assert (
        client.get(
            f"/api/v1/other-transports/{record_id}", headers=auth_headers(token_b)
        ).status_code
        == 404
    )
    assert (
        client.patch(
            f"/api/v1/other-transports/{record_id}",
            json={"seat": "9Z"},
            headers=auth_headers(token_b),
        ).status_code
        == 404
    )
    assert (
        client.delete(
            f"/api/v1/other-transports/{record_id}", headers=auth_headers(token_b)
        ).status_code
        == 404
    )


def test_transport_types_are_isolated(client):
    """An 'other' id must 404 on flight/train endpoints and vice versa (spec #11)."""
    token = register_and_login(client, "transport_iso")["access_token"]
    headers = auth_headers(token)

    flight = client.post(
        "/api/v1/flights", json={"origin": "HKG", "destination": "SIN"}, headers=headers
    ).json()
    other = client.post("/api/v1/other-transports", json=TRANSPORT, headers=headers).json()

    assert (
        client.get(f"/api/v1/other-transports/{flight['id']}", headers=headers).status_code == 404
    )
    assert client.get(f"/api/v1/flights/{other['id']}", headers=headers).status_code == 404
    assert client.get("/api/v1/other-transports", headers=headers).json()["total"] == 1
    assert client.get("/api/v1/flights", headers=headers).json()["total"] == 1


def test_transport_appears_in_timeline_and_dashboard(client):
    token = register_and_login(client, "transport_tl")["access_token"]
    headers = auth_headers(token)

    client.post("/api/v1/other-transports", json=TRANSPORT, headers=headers)

    timeline = client.get("/api/v1/timeline", headers=headers).json()
    assert len(timeline) == 1
    assert timeline[0]["type"] == "other"

    stats = client.get("/api/v1/dashboard", headers=headers).json()["stats"]
    assert stats["transports"] == 1
    assert stats["journeys"] == 1


def test_transport_requires_auth(client):
    assert client.get("/api/v1/other-transports").status_code == 401
