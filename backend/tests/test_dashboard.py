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
    assert body["by_month"] == []


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

    # Rolling trend source: chronological month buckets.
    assert body["by_month"] == [
        {"label": "2026-09", "name": None, "count": 1},
        {"label": "2026-10", "name": None, "count": 1},
    ]

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


def test_dashboard_upcoming_excludes_cancelled_and_completed(client):
    token = register_and_login(client, "upcoming_status")["access_token"]
    headers = auth_headers(token)
    for status, number, day in (
        ("cancelled", "CANCEL", "01"),
        ("completed", "DONE", "02"),
        ("scheduled", "ACTIVE", "03"),
    ):
        response = client.post(
            "/api/v1/trains",
            json={
                "origin": "北京南",
                "destination": "上海虹桥",
                "service_number": number,
                "status": status,
                "departure_time": f"2099-01-{day}T08:00:00Z",
            },
            headers=headers,
        )
        assert response.status_code == 201, response.text
    body = client.get("/api/v1/dashboard", headers=headers).json()
    assert body["upcoming"]["service_number"] == "ACTIVE"
    assert body["stats"]["trains"] == 3  # record counts are unchanged


def test_activity_dates_use_departure_zone(client):
    token = register_and_login(client, "local_activity")["access_token"]
    headers = auth_headers(token)
    response = client.post(
        "/api/v1/flights",
        json={
            **FLIGHT_HKG_SIN,
            "departure_time": "2026-01-31T23:30:00Z",
            "departure_timezone": "Asia/Hong_Kong",
            "arrival_timezone": "Asia/Singapore",
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    dashboard = client.get("/api/v1/dashboard", headers=headers).json()
    statistics = client.get("/api/v1/statistics", headers=headers).json()
    assert dashboard["by_month"][0]["label"] == "2026-02"
    assert statistics["by_day"][0]["label"] == "2026-02-01"
    assert dashboard["recent"][0]["departure_timezone"] == "Asia/Hong_Kong"
    assert dashboard["recent"][0]["arrival_timezone"] == "Asia/Singapore"


def test_activity_dates_cross_dst_and_default_utc(client):
    token = register_and_login(client, "dst_activity")["access_token"]
    headers = auth_headers(token)
    for number, time, zone in (
        ("WINTER", "2026-01-01T04:30:00Z", "America/New_York"),
        ("SUMMER", "2026-07-01T03:30:00Z", "America/New_York"),
        ("NOZONE", "2026-08-01T00:30:00Z", None),
    ):
        response = client.post(
            "/api/v1/trains",
            json={
                "origin": "New York",
                "destination": "Boston",
                "service_number": number,
                "departure_time": time,
                "departure_timezone": zone,
            },
            headers=headers,
        )
        assert response.status_code == 201, response.text
    labels = [
        item["label"] for item in client.get("/api/v1/statistics", headers=headers).json()["by_day"]
    ]
    assert labels == ["2025-12-31", "2026-06-30", "2026-08-01"]


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


def test_dashboard_and_statistics_cities_match_with_trains(client):
    """Overview and statistics must report the same city count (spec #10/#28).

    Train/other endpoints are free-text stations; both pages must include them.
    Regression: overview used to drop non-airport endpoints while statistics
    counted them, so the two numbers diverged.
    """
    token = register_and_login(client, "city_match")["access_token"]
    headers = auth_headers(token)

    client.post("/api/v1/flights", json=FLIGHT_HKG_SIN, headers=headers)  # HKG, SIN
    train = {
        "origin": "北京南",
        "destination": "上海虹桥",
        "departure_time": "2026-09-26T08:00:00Z",
        "arrival_time": "2026-09-26T12:28:00Z",
        "carrier": "中国铁路",
        "service_number": "G1",
    }
    assert client.post("/api/v1/trains", json=train, headers=headers).status_code == 201

    dash = client.get("/api/v1/dashboard", headers=headers).json()
    stats = client.get("/api/v1/statistics", headers=headers).json()

    dash_cities = dash["stats"]["cities"]
    stats_cities = stats["totals"]["cities"]
    assert dash_cities == stats_cities
    # Both include the two free-text train stations on top of airport cities.
    assert dash_cities >= 4


def test_city_totals_merge_verified_station_aliases_and_airports(client):
    token = register_and_login(client, "city_alias")["access_token"]
    headers = auth_headers(token)
    for record in (
        {"origin": "PEK", "destination": "SHA"},
        {"origin": "北京南", "destination": "上海虹桥"},
        {"origin": "北京西", "destination": "上海南"},
    ):
        endpoint = "/api/v1/flights" if record["origin"] == "PEK" else "/api/v1/trains"
        response = client.post(endpoint, json=record, headers=headers)
        assert response.status_code == 201, response.text
    dash = client.get("/api/v1/dashboard", headers=headers).json()
    stats = client.get("/api/v1/statistics", headers=headers).json()
    assert dash["stats"]["cities"] == stats["totals"]["cities"] == 2


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
