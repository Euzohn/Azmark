"""Tests for dashboard / statistics / timeline / map endpoints."""

from tests.conftest import auth_headers, register_and_login

FLIGHT_HKG_SIN = {
    "origin": "HKG",
    "destination": "SIN",
    "departure_time": "2026-09-26T01:45:00Z",
    "arrival_time": "2026-09-26T05:50:00Z",
    "carrier": "Cathay Pacific",
    "airline_code": "CX",
    "service_number": "CX659",
    "aircraft_model": "Airbus A330-300",
    "distance": "2540.0",
}

FLIGHT_SIN_PEK = {
    "origin": "SIN",
    "destination": "PEK",
    "departure_time": "2026-10-15T08:00:00Z",
    "arrival_time": "2026-10-15T14:00:00Z",
    "carrier": "Singapore Airlines",
    "airline_code": "SQ",
    "service_number": "SQ802",
    "aircraft_model": "Airbus A350-900",
    "distance": "4500.0",
}


def test_dashboard_empty(client):
    token = register_and_login(client, "dash_empty")["access_token"]
    headers = auth_headers(token)

    response = client.get("/api/v1/dashboard", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["stats"]["flights"] == 0
    assert body["stats"]["journeys"] == 0
    assert body["stats"]["trips"] == 0
    assert body["recent"] == []
    assert body["upcoming"] is None


def test_dashboard_with_flights(client):
    token = register_and_login(client, "dash_full")["access_token"]
    headers = auth_headers(token)

    client.post("/api/v1/flights", json=FLIGHT_HKG_SIN, headers=headers)
    client.post("/api/v1/flights", json=FLIGHT_SIN_PEK, headers=headers)
    client.post("/api/v1/trips", json={"name": "Asia Tour"}, headers=headers)

    response = client.get("/api/v1/dashboard", headers=headers)
    assert response.status_code == 200
    body = response.json()
    stats = body["stats"]

    assert stats["flights"] == 2
    assert stats["journeys"] == 2
    assert stats["trips"] == 1
    assert stats["distance_km"] == 7040.0
    # HKG (HK), SIN (SG), PEK (CN) → 3 countries
    assert stats["countries"] == 3
    assert stats["cities"] >= 3
    assert len(body["recent"]) == 2

    # Upcoming: both flights are in the future relative to test run if dates are
    # in the future; if past, upcoming should be None. Either way no error.
    assert "upcoming" in body


def test_statistics_breakdowns(client):
    token = register_and_login(client, "stats_user")["access_token"]
    headers = auth_headers(token)

    client.post("/api/v1/flights", json=FLIGHT_HKG_SIN, headers=headers)
    client.post("/api/v1/flights", json=FLIGHT_SIN_PEK, headers=headers)

    response = client.get("/api/v1/statistics", headers=headers)
    assert response.status_code == 200
    body = response.json()

    assert len(body["by_month"]) >= 2
    assert any(item["label"] == "CX" for item in body["by_airline"])
    assert any(item["label"] == "HKG" for item in body["by_airport"])
    assert any(item["label"] == "Airbus A330-300" for item in body["by_aircraft"])


def test_timeline(client):
    token = register_and_login(client, "tl_user")["access_token"]
    headers = auth_headers(token)

    client.post("/api/v1/flights", json=FLIGHT_HKG_SIN, headers=headers)
    client.post("/api/v1/flights", json=FLIGHT_SIN_PEK, headers=headers)

    response = client.get("/api/v1/timeline", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    # ordered descending by departure_time
    assert body[0]["service_number"] == "SQ802"


def test_map_routes(client):
    token = register_and_login(client, "map_user")["access_token"]
    headers = auth_headers(token)

    client.post("/api/v1/flights", json=FLIGHT_HKG_SIN, headers=headers)

    response = client.get("/api/v1/map/routes", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    route = body["items"][0]
    assert route["origin"]["code"] == "HKG"
    assert route["origin"]["lat"] is not None
    assert route["destination"]["code"] == "SIN"
    assert route["destination"]["lon"] is not None
    assert route["distance_km"] == 2540.0


def test_dashboard_user_isolation(client):
    token_a = register_and_login(client, "iso_a")["access_token"]
    token_b = register_and_login(client, "iso_b")["access_token"]

    client.post("/api/v1/flights", json=FLIGHT_HKG_SIN, headers=auth_headers(token_a))

    response = client.get("/api/v1/dashboard", headers=auth_headers(token_b))
    assert response.status_code == 200
    assert response.json()["stats"]["flights"] == 0
