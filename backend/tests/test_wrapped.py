"""Tests for the annual Travel Wrapped endpoint (spec #87)."""

from datetime import UTC, datetime

from tests.conftest import auth_headers, register_and_login


def _headers(client, username: str) -> dict[str, str]:
    return auth_headers(register_and_login(client, username)["access_token"])


def test_wrapped_empty_user(client):
    headers = _headers(client, "wrapped_empty")
    response = client.get("/api/v1/statistics/wrapped", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["available_years"] == []
    assert body["year"] == datetime.now(UTC).year
    assert body["totals"]["flights"] == 0
    assert body["totals"]["distance_km"] == 0.0
    assert body["longest_route"] is None
    assert body["first_journey"] is None
    assert float(body["spend"]["converted_total"]) == 0


def test_wrapped_year_assignment_and_available_years(client):
    headers = _headers(client, "wrapped_years")
    for day, number in (("2025-06-01", "CX1"), ("2025-08-02", "CX2"), ("2026-03-01", "MU9")):
        assert (
            client.post(
                "/api/v1/flights",
                json={
                    "origin": "HKG",
                    "destination": "SIN",
                    "airline_code": "CX",
                    "service_number": number,
                    "departure_time": f"{day}T01:45:00Z",
                    "arrival_time": f"{day}T05:50:00Z",
                },
                headers=headers,
            ).status_code
            == 201
        )

    default = client.get("/api/v1/statistics/wrapped", headers=headers).json()
    assert default["available_years"] == [2025, 2026]
    # No explicit year -> the newest one.
    assert default["year"] == 2026
    assert default["totals"]["flights"] == 1

    older = client.get("/api/v1/statistics/wrapped", params={"year": 2025}, headers=headers).json()
    assert older["year"] == 2025
    assert older["totals"]["flights"] == 2
    assert [item["label"] for item in older["by_month"]] == ["2025-06", "2025-08"]


def test_wrapped_uses_departure_timezone_for_the_year_boundary(client):
    headers = _headers(client, "wrapped_tz")
    # 2025-12-31T16:30Z is 2026-01-01 00:30 in Asia/Shanghai: a 2026 departure.
    client.post(
        "/api/v1/flights",
        json={
            "origin": "PEK",
            "destination": "SHA",
            "airline_code": "CA",
            "service_number": "CA1883",
            "departure_time": "2025-12-31T16:30:00Z",
            "arrival_time": "2026-01-01T00:10:00Z",
            "departure_timezone": "Asia/Shanghai",
            "arrival_timezone": "Asia/Shanghai",
        },
        headers=headers,
    )

    body = client.get("/api/v1/statistics/wrapped", headers=headers).json()
    assert body["year"] == 2026
    assert body["first_journey"] == "2026-01-01"


def test_wrapped_records_without_departure_time_are_skipped(client):
    headers = _headers(client, "wrapped_nodep")
    client.post(
        "/api/v1/flights",
        json={"origin": "HKG", "destination": "SIN", "service_number": "CX0"},
        headers=headers,
    )

    body = client.get("/api/v1/statistics/wrapped", headers=headers).json()
    assert body["available_years"] == []
    assert body["totals"]["flights"] == 0


def test_wrapped_mixed_modules(client):
    headers = _headers(client, "wrapped_mix")
    client.post(
        "/api/v1/flights",
        json={
            "origin": "HKG",
            "destination": "SIN",
            "airline_code": "CX",
            "service_number": "CX659",
            "departure_time": "2026-09-26T01:45:00Z",
            "arrival_time": "2026-09-26T05:50:00Z",
            "distance": "2540.0",
            "aircraft_model": "Airbus A330-300",
        },
        headers=headers,
    )
    trip = client.post(
        "/api/v1/trips", json={"name": "SG 2026", "start_date": "2026-09-26"}, headers=headers
    ).json()
    train = client.post(
        "/api/v1/trains",
        json={
            "origin": "上海虹桥",
            "destination": "北京南",
            "carrier": "中国铁路",
            "service_number": "G2",
            "departure_time": "2026-04-01T01:00:00Z",
            "arrival_time": "2026-04-01T06:00:00Z",
            "trip_id": trip["id"],
        },
        headers=headers,
    ).json()
    # Second Shanghai leg makes 上海 the most-visited city (2 visits).
    client.post(
        "/api/v1/trains",
        json={
            "origin": "上海虹桥",
            "destination": "苏州",
            "carrier": "中国铁路",
            "service_number": "G7002",
            "departure_time": "2026-05-01T01:00:00Z",
            "arrival_time": "2026-05-01T01:25:00Z",
        },
        headers=headers,
    )
    client.post(
        "/api/v1/hotels",
        json={
            "hotel": "Marina Bay Sands",
            "check_in": "2026-09-26",
            "check_out": "2026-09-29",
        },
        headers=headers,
    )
    client.post(
        "/api/v1/activities",
        json={"name": "Light show", "start_at": "2026-09-30T11:00:00Z"},
        headers=headers,
    )
    client.post(
        "/api/v1/expenses",
        json={"amount": "100.00", "currency": "CNY", "occurred_at": "2026-09-27T12:00:00Z"},
        headers=headers,
    )
    client.post(
        "/api/v1/expenses",
        json={"amount": "999.00", "currency": "CNY", "occurred_at": "2025-01-01T12:00:00Z"},
        headers=headers,
    )

    body = client.get("/api/v1/statistics/wrapped", headers=headers).json()
    totals = body["totals"]
    assert totals["flights"] == 1
    assert totals["trains"] == 2
    assert totals["hotels"] == 1
    assert totals["hotel_nights"] == 3
    assert totals["activities"] == 1
    assert totals["trips"] == 1
    # Three journeys on distinct days.
    assert totals["travel_days"] == 3
    # The longest journey is one of the two; HKG-SIN (2540 km explicit) beats
    # the Shanghai-Beijing city/registry fallback (~1000+ km), so it must win.
    assert body["longest_route"]["origin"]["code"] == "HKG"
    assert body["longest_route"]["distance_km"] == 2540.0
    # Spend is scoped to the year: only the 100.00 expense belongs to 2026.
    assert float(body["spend"]["converted_total"]) == 100.00
    # Stations come from trains/other transport only (flights use airports).
    assert {item["label"] for item in body["top_stations"]} == {"上海虹桥", "北京南", "苏州"}
    assert train["service_number"] == "G2"
    # spec #87: aircraft (flight only), most-visited city and favorite trip.
    assert [item["label"] for item in body["top_aircraft"]] == ["Airbus A330-300"]
    assert body["most_visited_city"]["label"] == "上海"
    assert body["most_visited_city"]["count"] == 2
    assert body["favorite_trip"]["label"] == "SG 2026"
    assert body["favorite_trip"]["count"] == 1


def test_wrapped_user_isolation(client):
    headers_a = _headers(client, "wrapped_iso_a")
    headers_b = _headers(client, "wrapped_iso_b")
    client.post(
        "/api/v1/flights",
        json={
            "origin": "HKG",
            "destination": "SIN",
            "service_number": "CX659",
            "departure_time": "2026-09-26T01:45:00Z",
        },
        headers=headers_a,
    )

    body = client.get("/api/v1/statistics/wrapped", headers=headers_b).json()
    assert body["totals"]["flights"] == 0
    assert body["available_years"] == []


def test_wrapped_year_validation(client):
    headers = _headers(client, "wrapped_valid")
    too_early = client.get("/api/v1/statistics/wrapped", params={"year": 1899}, headers=headers)
    assert too_early.status_code == 422
    too_late = client.get("/api/v1/statistics/wrapped", params={"year": 2201}, headers=headers)
    assert too_late.status_code == 422


def test_wrapped_requires_auth(client):
    assert client.get("/api/v1/statistics/wrapped").status_code == 401


def test_wrapped_longest_route_uses_haversine_fallback(client):
    """A journey without a stored distance still competes for longest route.

    The SQL pass sums stored distances; rows without one resolve endpoints
    from the reference data in Python. The single-row refetch must return the
    full record (type, carrier, endpoints) for the winner.
    """
    headers = _headers(client, "wrapped_haversine")
    client.post(
        "/api/v1/flights",
        json={
            "origin": "HKG",
            "destination": "SIN",
            "carrier": "Cathay Pacific",
            "service_number": "CX659",
            "departure_time": "2026-09-26T01:45:00Z",
            "arrival_time": "2026-09-26T05:50:00Z",
        },
        headers=headers,
    )
    client.post(
        "/api/v1/trains",
        json={
            "origin": "上海虹桥",
            "destination": "苏州",
            "service_number": "G7002",
            "departure_time": "2026-10-01T01:00:00Z",
            "arrival_time": "2026-10-01T01:25:00Z",
            "distance": "100.0",
        },
        headers=headers,
    )

    body = client.get("/api/v1/statistics/wrapped", headers=headers).json()
    route = body["longest_route"]
    assert route["origin"]["code"] == "HKG"
    assert route["destination"]["code"] == "SIN"
    assert route["type"] == "flight"
    assert route["carrier"] == "Cathay Pacific"
    assert route["distance_km"] > 2000
    # One stored distance (100 km) plus one haversine value, rounded once.
    assert body["totals"]["distance_km"] == round(100 + route["distance_km"], 1)


def test_wrapped_leaderboards_exclude_blank_values(client):
    """Blank strings must stay out of the wrapped leaderboards.

    The Python loop guarded every Counter with ``if value:``; the GROUP BY
    queries reproduce that with ``IS NOT NULL AND != ''``. The airline key is
    ``airline_code or carrier``, so a blank code falls back to the carrier.
    """
    headers = _headers(client, "wrapped_blank")
    client.post(
        "/api/v1/flights",
        json={
            "origin": "PEK",
            "destination": "SFO",
            "carrier": "",
            "airline_code": "",
            "service_number": "CA983",
            "departure_time": "2026-08-01T08:00:00Z",
            "arrival_time": "2026-08-01T11:30:00Z",
            "aircraft_model": "",
        },
        headers=headers,
    )
    client.post(
        "/api/v1/flights",
        json={
            "origin": "HKG",
            "destination": "SIN",
            "carrier": "Cathay Pacific",
            "service_number": "CX659",
            "departure_time": "2026-08-02T01:45:00Z",
            "arrival_time": "2026-08-02T05:50:00Z",
            "aircraft_model": "Airbus A330-300",
        },
        headers=headers,
    )

    body = client.get("/api/v1/statistics/wrapped", headers=headers).json()
    assert body["totals"]["flights"] == 2
    assert [(item["label"], item["count"]) for item in body["top_airlines"]] == [
        ("Cathay Pacific", 1)
    ]
    assert [item["label"] for item in body["top_aircraft"]] == ["Airbus A330-300"]


def test_wrapped_aggregates_merge_across_id_chunks(client, monkeypatch):
    """Year-scoped GROUP BY queries batch large ``id IN (...)`` lists.

    Shrink the batch size to force several queries and verify the merged
    counters keep exact totals and the deterministic count-DESC ordering.
    """
    from app.services.dashboard import DashboardService

    monkeypatch.setattr(DashboardService, "_ID_CHUNK", 2)

    headers = _headers(client, "wrapped_chunks")
    for origin, destination, code, number, day in (
        ("HKG", "SIN", "CX", "CX659", "2026-03-01"),
        ("SIN", "HKG", "CX", "CX660", "2026-03-02"),
        ("PEK", "SFO", "SQ", "SQ802", "2026-04-01"),
    ):
        response = client.post(
            "/api/v1/flights",
            json={
                "origin": origin,
                "destination": destination,
                "airline_code": code,
                "service_number": number,
                "departure_time": f"{day}T01:00:00Z",
                "arrival_time": f"{day}T05:00:00Z",
            },
            headers=headers,
        )
        assert response.status_code == 201, response.text

    body = client.get("/api/v1/statistics/wrapped", headers=headers).json()
    assert body["totals"]["flights"] == 3
    assert [(item["label"], item["count"]) for item in body["top_airlines"]] == [
        ("CX", 2),
        ("SQ", 1),
    ]
    by_airport = {item["label"]: item["count"] for item in body["top_airports"]}
    assert by_airport == {"HKG": 2, "SIN": 2, "PEK": 1, "SFO": 1}
    assert [(item["label"], item["count"]) for item in body["by_month"]] == [
        ("2026-03", 2),
        ("2026-04", 1),
    ]
