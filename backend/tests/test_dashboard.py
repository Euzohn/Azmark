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


def test_dashboard_recent_and_upcoming_are_cross_type(client):
    token = register_and_login(client, "dash_cross")["access_token"]
    headers = auth_headers(token)

    train = {
        "origin": "北京南",
        "destination": "上海虹桥",
        "departure_time": "2099-01-01T08:00:00Z",
        "arrival_time": "2099-01-01T12:28:00Z",
        "carrier": "中国铁路",
        "service_number": "G1",
    }
    flight = {
        **FLIGHT_HKG_SIN,
        "departure_time": "2099-02-01T08:00:00Z",
        "arrival_time": "2099-02-01T12:00:00Z",
    }
    assert client.post("/api/v1/trains", json=train, headers=headers).status_code == 201
    assert client.post("/api/v1/flights", json=flight, headers=headers).status_code == 201

    body = client.get("/api/v1/dashboard", headers=headers).json()
    assert {record["type"] for record in body["recent"]} == {"flight", "train"}
    # The earliest future departure wins, regardless of transport type.
    assert body["upcoming"]["type"] == "train"
    assert body["upcoming"]["service_number"] == "G1"


def test_statistics_breakdowns(client):
    token = register_and_login(client, "stats_user")["access_token"]
    headers = auth_headers(token)

    client.post("/api/v1/flights", json=FLIGHT_HKG_SIN, headers=headers)
    client.post("/api/v1/flights", json=FLIGHT_SIN_PEK, headers=headers)

    response = client.get("/api/v1/statistics", headers=headers)
    assert response.status_code == 200
    body = response.json()

    assert body["totals"]["flights"] == 2
    assert body["totals"]["trips"] == 0
    assert body["totals"]["distance_km"] == 7040.0
    assert len(body["by_year"]) == 1
    assert len(body["by_month"]) >= 2
    assert len(body["by_day"]) >= 2
    assert any(item["label"] == "CX" for item in body["by_airline"])
    assert any(item["label"] == "HKG" for item in body["by_airport"])
    assert any(item["label"] == "Airbus A330-300" for item in body["by_aircraft"])
    assert body["by_cabin"] == []
    assert body["by_train_operator"] == []


def test_statistics_by_alliance(client):
    token = register_and_login(client, "stats_alliance")["access_token"]
    headers = auth_headers(token)

    client.post("/api/v1/flights", json=FLIGHT_HKG_SIN, headers=headers)  # CX -> oneworld
    client.post("/api/v1/flights", json=FLIGHT_SIN_PEK, headers=headers)  # SQ -> star_alliance

    response = client.get("/api/v1/statistics", headers=headers)
    assert response.status_code == 200
    body = response.json()

    assert body["by_alliance"]
    by_alliance = {item["label"]: item["count"] for item in body["by_alliance"]}
    assert by_alliance["star_alliance"] == 1
    assert by_alliance["oneworld"] == 1


def test_statistics_overall_and_train_breakdowns(client):
    token = register_and_login(client, "stats_train")["access_token"]
    headers = auth_headers(token)

    client.post(
        "/api/v1/flights",
        json={
            **FLIGHT_HKG_SIN,
            "cabin_class": "business",
            "seat_type": "window",
        },
        headers=headers,
    )
    train = {
        "origin": "北京南",
        "destination": "上海虹桥",
        "departure_time": "2026-09-26T08:00:00Z",
        "arrival_time": "2026-09-26T12:28:00Z",
        "carrier": "中国铁路",
        "service_number": "G1",
        "train_type": "high_speed",
        "cabin_class": "business",
        "seat_type": "window",
        "distance": "1318.0",
    }
    response = client.post("/api/v1/trains", json=train, headers=headers)
    assert response.status_code == 201, response.text
    client.post("/api/v1/trips", json={"name": "Stats trip"}, headers=headers)

    response = client.get("/api/v1/statistics", headers=headers)
    assert response.status_code == 200
    body = response.json()

    totals = body["totals"]
    assert totals["countries"] == 2  # HKG, SIN
    assert totals["cities"] >= 4
    assert totals["flights"] == 1
    assert totals["trains"] == 1
    assert totals["transports"] == 0
    assert totals["trips"] == 1
    assert totals["distance_km"] == 3858.0

    assert {item["label"]: item["count"] for item in body["by_cabin"]} == {"business": 1}
    assert {item["label"]: item["count"] for item in body["by_seat_type"]} == {"window": 1}
    assert {item["label"]: item["count"] for item in body["by_train_operator"]} == {"中国铁路": 1}
    assert {item["label"]: item["count"] for item in body["by_train_type"]} == {"high_speed": 1}
    assert {item["label"]: item["count"] for item in body["by_station"]} == {
        "北京南": 1,
        "上海虹桥": 1,
    }
    assert {item["label"]: item["count"] for item in body["by_train_class"]} == {"business": 1}
    assert {item["label"]: item["count"] for item in body["by_train_seat_type"]} == {"window": 1}
    assert [item["label"] for item in body["by_year"]] == ["2026"]
    assert any(item["label"] == "2026-09-26" and item["count"] == 2 for item in body["by_day"])


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
