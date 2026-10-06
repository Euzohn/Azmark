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
