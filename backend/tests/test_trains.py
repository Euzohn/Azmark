import uuid

from tests.conftest import auth_headers, register_and_login

TRAIN = {
    "origin": "北京南",
    "destination": "上海虹桥",
    "departure_time": "2026-09-26T08:00:00Z",
    "arrival_time": "2026-09-26T12:28:00Z",
    "carrier": "中国铁路",
    "service_number": "G1",
    "train_type": "high_speed",
    "cabin_class": "business",
    "carriage": "08",
    "seat": "12A",
    "seat_type": "window",
    "ticket_type": "reserved",
    "price": "553.00",
    "currency": "CNY",
}


def test_create_and_list_train(client):
    token = register_and_login(client, "trainer")["access_token"]
    headers = auth_headers(token)

    response = client.post("/api/v1/trains", json=TRAIN, headers=headers)
    assert response.status_code == 201, response.text
    created = response.json()
    assert created["type"] == "train"
    assert created["service_number"] == "G1"
    assert created["train_type"] == "high_speed"
    assert created["carriage"] == "08"
    assert created["seat_type"] == "window"
    assert created["ticket_type"] == "reserved"

    response = client.get("/api/v1/trains", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == created["id"]


def test_train_crud_and_search(client):
    token = register_and_login(client, "train_crud")["access_token"]
    headers = auth_headers(token)

    created = client.post("/api/v1/trains", json=TRAIN, headers=headers).json()

    response = client.get("/api/v1/trains", params={"search": "G1"}, headers=headers)
    assert response.json()["total"] == 1

    response = client.get("/api/v1/trains", params={"search": "D999"}, headers=headers)
    assert response.json()["total"] == 0

    response = client.patch(
        f"/api/v1/trains/{created['id']}", json={"seat": "13C"}, headers=headers
    )
    assert response.status_code == 200
    assert response.json()["seat"] == "13C"
    assert response.json()["service_number"] == "G1"

    response = client.delete(f"/api/v1/trains/{created['id']}", headers=headers)
    assert response.status_code == 204
    assert client.get(f"/api/v1/trains/{created['id']}", headers=headers).status_code == 404


def test_train_sensitive_encrypted_at_rest(client, db):
    from sqlalchemy import select

    from app.core.crypto import decrypt_value
    from app.models.transport_record import TransportRecord

    token = register_and_login(client, "train_cred")["access_token"]
    headers = auth_headers(token)

    payload = {
        **TRAIN,
        "purchase_credential": "123456789012345678",
        "purchase_credential_type": "id_card",
        "ticket_number": "E123456789",
    }
    created = client.post("/api/v1/trains", json=payload, headers=headers).json()
    assert created["purchase_credential"] == "123456789012345678"
    assert created["ticket_number"] == "E123456789"

    row = db.scalar(select(TransportRecord).where(TransportRecord.id == uuid.UUID(created["id"])))
    assert row is not None
    assert row.type == "train"
    for enc, plain in (
        ("purchase_credential_enc", "123456789012345678"),
        ("ticket_number_enc", "E123456789"),
    ):
        assert getattr(row, enc) != plain
        assert decrypt_value(getattr(row, enc)) == plain


def test_train_user_isolation(client):
    token_a = register_and_login(client, "train_a")["access_token"]
    token_b = register_and_login(client, "train_b")["access_token"]

    created = client.post("/api/v1/trains", json=TRAIN, headers=auth_headers(token_a)).json()
    record_id = created["id"]

    assert client.get("/api/v1/trains", headers=auth_headers(token_b)).json()["total"] == 0
    assert (
        client.get(f"/api/v1/trains/{record_id}", headers=auth_headers(token_b)).status_code == 404
    )
    assert (
        client.patch(
            f"/api/v1/trains/{record_id}", json={"seat": "9Z"}, headers=auth_headers(token_b)
        ).status_code
        == 404
    )
    assert (
        client.delete(f"/api/v1/trains/{record_id}", headers=auth_headers(token_b)).status_code
        == 404
    )


def test_flight_and_train_are_isolated_by_type(client):
    """A flight id must 404 on the trains endpoint and vice versa (spec #11)."""
    token = register_and_login(client, "type_iso")["access_token"]
    headers = auth_headers(token)

    flight = client.post(
        "/api/v1/flights",
        json={"origin": "HKG", "destination": "SIN", "service_number": "CX659"},
        headers=headers,
    ).json()
    train = client.post("/api/v1/trains", json=TRAIN, headers=headers).json()

    assert client.get(f"/api/v1/trains/{flight['id']}", headers=headers).status_code == 404
    assert client.get(f"/api/v1/flights/{train['id']}", headers=headers).status_code == 404
    # And each list only shows its own type.
    assert client.get("/api/v1/trains", headers=headers).json()["total"] == 1
    assert client.get("/api/v1/flights", headers=headers).json()["total"] == 1


def test_train_requires_auth(client):
    assert client.get("/api/v1/trains").status_code == 401
