import uuid

from tests.conftest import auth_headers, register_and_login

TRIP = {
    "name": "Tokyo 2026",
    "description": "Golden Week trip",
    "start_date": "2026-04-29",
    "end_date": "2026-05-05",
    "origin": "HKG",
    "destination": "TYO",
    "status": "planned",
}


def _make_flight(origin="HKG", destination="NRT"):
    return {
        "origin": origin,
        "destination": destination,
        "departure_time": "2026-04-29T01:45:00Z",
        "arrival_time": "2026-04-29T06:10:00Z",
        "carrier": "Cathay Pacific",
        "service_number": "CX524",
        "seat": "23F",
    }


def test_create_and_list_trip(client):
    token = register_and_login(client, "trip_list")["access_token"]
    headers = auth_headers(token)

    response = client.post("/api/v1/trips", json=TRIP, headers=headers)
    assert response.status_code == 201, response.text
    created = response.json()
    assert created["name"] == "Tokyo 2026"
    assert created["status"] == "planned"

    response = client.get("/api/v1/trips", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == created["id"]


def test_trip_grouping_flights(client):
    """Flights carry trip_id and appear in TripDetail (spec #15/#16 decision)."""
    token = register_and_login(client, "trip_group")["access_token"]
    headers = auth_headers(token)

    trip = client.post("/api/v1/trips", json=TRIP, headers=headers).json()
    flight = client.post(
        "/api/v1/flights", json={**_make_flight(), "trip_id": trip["id"]}, headers=headers
    )
    assert flight.status_code == 201, flight.text
    assert flight.json()["trip_id"] == trip["id"]

    response = client.get(f"/api/v1/trips/{trip['id']}", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == trip["id"]
    assert [f["id"] for f in body["flights"]] == [flight.json()["id"]]


def test_update_and_delete_trip(client):
    token = register_and_login(client, "trip_crud")["access_token"]
    headers = auth_headers(token)

    trip = client.post("/api/v1/trips", json=TRIP, headers=headers).json()
    flight = client.post(
        "/api/v1/flights", json={**_make_flight(), "trip_id": trip["id"]}, headers=headers
    ).json()

    response = client.patch(
        f"/api/v1/trips/{trip['id']}", json={"name": "Tokyo Revised"}, headers=headers
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Tokyo Revised"

    response = client.delete(f"/api/v1/trips/{trip['id']}", headers=headers)
    assert response.status_code == 204

    response = client.get(f"/api/v1/trips/{trip['id']}", headers=headers)
    assert response.status_code == 404

    # The flight must survive the trip deletion (trip_id reset, spec #57).
    response = client.get(f"/api/v1/flights/{flight['id']}", headers=headers)
    assert response.status_code == 200
    assert response.json()["trip_id"] is None


def test_invalid_trip_dates(client):
    token = register_and_login(client, "trip_dates")["access_token"]
    response = client.post(
        "/api/v1/trips",
        json={**TRIP, "end_date": "2026-04-01"},
        headers=auth_headers(token),
    )
    assert response.status_code == 422


def test_trip_user_isolation(client):
    """User A must never read/modify/delete User B trips (spec #57/#73)."""
    token_a = register_and_login(client, "trip_user_a")["access_token"]
    token_b = register_and_login(client, "trip_user_b")["access_token"]

    trip = client.post("/api/v1/trips", json=TRIP, headers=auth_headers(token_a)).json()
    trip_id = trip["id"]

    response = client.get("/api/v1/trips", headers=auth_headers(token_b))
    assert response.status_code == 200
    assert response.json()["total"] == 0

    response = client.get(f"/api/v1/trips/{trip_id}", headers=auth_headers(token_b))
    assert response.status_code == 404

    response = client.patch(
        f"/api/v1/trips/{trip_id}", json={"name": "Stolen"}, headers=auth_headers(token_b)
    )
    assert response.status_code == 404

    response = client.delete(f"/api/v1/trips/{trip_id}", headers=auth_headers(token_b))
    assert response.status_code == 404

    response = client.get(f"/api/v1/trips/{trip_id}", headers=auth_headers(token_a))
    assert response.status_code == 200
    assert response.json()["name"] == "Tokyo 2026"


def test_trip_requires_auth(client):
    response = client.get("/api/v1/trips")
    assert response.status_code == 401


def test_invalid_trip_id(client):
    token = register_and_login(client, "trip_invalid")["access_token"]
    response = client.get(f"/api/v1/trips/{uuid.uuid4()}", headers=auth_headers(token))
    assert response.status_code == 404
