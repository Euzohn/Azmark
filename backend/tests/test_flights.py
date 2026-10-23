import uuid

from tests.conftest import auth_headers, register_and_login

FLIGHT = {
    "origin": "HKG",
    "destination": "SIN",
    "departure_time": "2026-09-26T01:45:00Z",
    "arrival_time": "2026-09-26T05:50:00Z",
    "departure_timezone": "Asia/Hong_Kong",
    "arrival_timezone": "Asia/Singapore",
    "carrier": "Cathay Pacific",
    "service_number": "CX659",
    "seat": "32A",
    "price": "2580.00",
    "currency": "CNY",
}


def test_cabin_class_roundtrip(client):
    token = register_and_login(client, "cabin_user")["access_token"]
    headers = auth_headers(token)

    created = client.post(
        "/api/v1/flights", json={**FLIGHT, "cabin_class": "business"}, headers=headers
    )
    assert created.status_code == 201, created.text
    assert created.json()["cabin_class"] == "business"

    updated = client.patch(
        f"/api/v1/flights/{created.json()['id']}",
        json={"cabin_class": "premium_economy"},
        headers=headers,
    )
    assert updated.status_code == 200
    assert updated.json()["cabin_class"] == "premium_economy"

    listed = client.get("/api/v1/flights", headers=headers).json()
    assert listed["items"][0]["cabin_class"] == "premium_economy"


def test_offset_timezone_normalized_to_iana(client):
    token = register_and_login(client, "tz_user")["access_token"]
    headers = auth_headers(token)

    created = client.post(
        "/api/v1/flights",
        json={**FLIGHT, "departure_timezone": "+08:00", "arrival_timezone": "+09:00"},
        headers=headers,
    )
    assert created.status_code == 201, created.text
    body = created.json()
    # VariFlight-style offsets are coerced to readable IANA names on write.
    assert body["departure_timezone"] == "Asia/Shanghai"
    assert body["arrival_timezone"] == "Asia/Tokyo"

    # A PATCH with an offset is normalized too, so edits never reintroduce the
    # mixed format.
    patched = client.patch(
        f"/api/v1/flights/{body['id']}",
        json={"arrival_timezone": "+05:30"},
        headers=headers,
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["arrival_timezone"] == "Asia/Kolkata"


def test_create_and_list_flight(client):
    token = register_and_login(client, "flighter")["access_token"]
    headers = auth_headers(token)

    response = client.post("/api/v1/flights", json=FLIGHT, headers=headers)
    assert response.status_code == 201, response.text
    created = response.json()
    assert created["type"] == "flight"
    assert created["service_number"] == "CX659"
    assert created["price"] == "2580.00"

    response = client.get("/api/v1/flights", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == created["id"]


def test_flight_crud_and_search(client):
    token = register_and_login(client, "crud")["access_token"]
    headers = auth_headers(token)

    created = client.post("/api/v1/flights", json=FLIGHT, headers=headers).json()

    response = client.get("/api/v1/flights", params={"search": "CX659"}, headers=headers)
    assert response.status_code == 200
    assert response.json()["total"] == 1

    response = client.get("/api/v1/flights", params={"search": "MU123"}, headers=headers)
    assert response.status_code == 200
    assert response.json()["total"] == 0

    response = client.patch(
        f"/api/v1/flights/{created['id']}", json={"seat": "33C"}, headers=headers
    )
    assert response.status_code == 200
    assert response.json()["seat"] == "33C"
    assert response.json()["service_number"] == "CX659"

    response = client.delete(f"/api/v1/flights/{created['id']}", headers=headers)
    assert response.status_code == 204
    response = client.get(f"/api/v1/flights/{created['id']}", headers=headers)
    assert response.status_code == 404


def test_user_isolation(client):
    """User A must never read/modify/delete User B records (spec #73)."""
    token_a = register_and_login(client, "user_a")["access_token"]
    token_b = register_and_login(client, "user_b")["access_token"]

    created = client.post("/api/v1/flights", json=FLIGHT, headers=auth_headers(token_a)).json()
    record_id = created["id"]

    response = client.get("/api/v1/flights", headers=auth_headers(token_b))
    assert response.status_code == 200
    assert response.json()["total"] == 0

    response = client.get(f"/api/v1/flights/{record_id}", headers=auth_headers(token_b))
    assert response.status_code == 404

    response = client.patch(
        f"/api/v1/flights/{record_id}", json={"seat": "99Z"}, headers=auth_headers(token_b)
    )
    assert response.status_code == 404

    response = client.delete(f"/api/v1/flights/{record_id}", headers=auth_headers(token_b))
    assert response.status_code == 404

    response = client.get(f"/api/v1/flights/{record_id}", headers=auth_headers(token_a))
    assert response.status_code == 200
    assert response.json()["seat"] == "32A"


def test_flight_requires_auth(client):
    response = client.get("/api/v1/flights")
    assert response.status_code == 401


def test_invalid_record_id(client):
    token = register_and_login(client, "invalid")["access_token"]
    response = client.get(f"/api/v1/flights/{uuid.uuid4()}", headers=auth_headers(token))
    assert response.status_code == 404


def test_purchase_credential_encrypted_at_rest(client, db):
    """Passport/ID is encrypted at rest; owner sees plaintext (spec #45/#96)."""
    from sqlalchemy import select

    from app.core.crypto import decrypt_value
    from app.models.transport_record import TransportRecord

    token = register_and_login(client, "cred_user")["access_token"]
    headers = auth_headers(token)

    payload = {
        **FLIGHT,
        "purchase_credential": "E12345678",
        "purchase_credential_type": "passport",
        "booking_reference": "ABCDEF",
        "ticket_number": "160-1234567890",
        "distance": "2580.5",
    }
    created = client.post("/api/v1/flights", json=payload, headers=headers).json()
    assert created["purchase_credential"] == "E12345678"
    assert created["purchase_credential_type"] == "passport"
    assert created["booking_reference"] == "ABCDEF"
    assert created["ticket_number"] == "160-1234567890"
    assert created["distance"] == "2580.50"

    row = db.scalar(select(TransportRecord).where(TransportRecord.id == uuid.UUID(created["id"])))
    assert row is not None
    # 证件类型是分类值，非敏感，明文存储。
    assert row.purchase_credential_type == "passport"
    for enc, plain in (
        ("purchase_credential_enc", "E12345678"),
        ("booking_reference_enc", "ABCDEF"),
        ("ticket_number_enc", "160-1234567890"),
    ):
        assert getattr(row, enc) != plain
        assert decrypt_value(getattr(row, enc)) == plain

    updated = client.patch(
        f"/api/v1/flights/{created['id']}",
        json={"booking_reference": None, "purchase_credential": None},
        headers=headers,
    )
    assert updated.status_code == 200
    assert updated.json()["booking_reference"] is None
    assert updated.json()["purchase_credential"] is None
    db.refresh(row)
    assert row.booking_reference_enc is None
    assert row.purchase_credential_enc is None


def test_flight_advanced_filters(client):
    token = register_and_login(client, "filter_user")["access_token"]
    headers = auth_headers(token)

    client.post(
        "/api/v1/flights",
        json={
            "origin": "HKG",
            "destination": "SIN",
            "service_number": "CX659",
            "status": "scheduled",
            "cabin_class": "economy",
            "departure_time": "2026-09-26T01:45:00Z",
        },
        headers=headers,
    )
    client.post(
        "/api/v1/flights",
        json={
            "origin": "PEK",
            "destination": "NRT",
            "service_number": "CA123",
            "status": "completed",
            "cabin_class": "business",
            "departure_time": "2026-03-01T02:00:00Z",
        },
        headers=headers,
    )
    trip = client.post(
        "/api/v1/trips",
        json={"name": "Japan", "start_date": "2026-03-01", "end_date": "2026-03-08"},
        headers=headers,
    ).json()
    client.post(
        "/api/v1/flights",
        json={
            "origin": "PEK",
            "destination": "HND",
            "service_number": "CA456",
            "status": "scheduled",
            "cabin_class": "business",
            "departure_time": "2026-03-02T02:00:00Z",
            "trip_id": trip["id"],
        },
        headers=headers,
    )

    def total(**params):
        response = client.get("/api/v1/flights", params=params, headers=headers)
        assert response.status_code == 200, response.text
        return response.json()["total"]

    assert total(status="scheduled") == 2
    assert total(status="completed") == 1
    assert total(cabin_class="business") == 2
    assert total(date_from="2026-03-01", date_to="2026-03-31") == 2
    assert total(trip_id=trip["id"]) == 1
    # Combined filters intersect.
    assert total(status="scheduled", cabin_class="business") == 1
    assert total(status="scheduled", date_from="2026-09-01") == 1


def test_create_duplicate_returns_conflict(client):
    """Same carrier+number+date+route → 409 with existing record (spec #41)."""
    token = register_and_login(client, "dup_user")["access_token"]
    headers = auth_headers(token)

    first = client.post("/api/v1/flights", json=FLIGHT, headers=headers)
    assert first.status_code == 201

    # Identical flight again → 409.
    dup = client.post("/api/v1/flights", json=FLIGHT, headers=headers)
    assert dup.status_code == 409
    detail = dup.json()["detail"]
    assert detail["existing_record"]["id"] == first.json()["id"]
    assert detail["existing_record"]["service_number"] == "CX659"

    # Force-create bypasses the check (spec #41 "Keep New").
    forced = client.post(
        "/api/v1/flights", json=FLIGHT, params={"force": "true"}, headers=headers
    )
    assert forced.status_code == 201
    assert forced.json()["id"] != first.json()["id"]

    # Different case / extra spaces still count as duplicate.
    mixed = client.post(
        "/api/v1/flights",
        json={**FLIGHT, "service_number": " cx659 ", "carrier": "cathay pacific"},
        headers=headers,
    )
    assert mixed.status_code == 409


def test_duplicate_only_within_same_user(client):
    """User A's flight is not a duplicate for User B (spec #57)."""
    token_a = register_and_login(client, "dup_a")["access_token"]
    token_b = register_and_login(client, "dup_b")["access_token"]

    first = client.post("/api/v1/flights", json=FLIGHT, headers=auth_headers(token_a))
    assert first.status_code == 201

    same = client.post("/api/v1/flights", json=FLIGHT, headers=auth_headers(token_b))
    assert same.status_code == 201  # not a duplicate across users
