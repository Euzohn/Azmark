from tests.conftest import auth_headers, register_and_login


def _create_records(client, headers):
    flight = client.post(
        "/api/v1/flights",
        json={
            "origin": "HKG",
            "destination": "NRT",
            "departure_time": "2026-04-29T01:45:00Z",
            "arrival_time": "2026-04-29T06:10:00Z",
            "carrier": "Cathay Pacific",
            "service_number": "CX524",
            "status": "scheduled",
        },
        headers=headers,
    )
    assert flight.status_code == 201, flight.text

    train = client.post(
        "/api/v1/trains",
        json={
            "origin": "SHA",
            "destination": "HGH",
            "departure_time": "2026-04-30T02:00:00Z",
            "arrival_time": "2026-04-30T03:00:00Z",
            "carrier": "China Railway",
            "service_number": "G100",
            "status": "completed",
        },
        headers=headers,
    )
    assert train.status_code == 201, train.text

    transport = client.post(
        "/api/v1/other-transports",
        json={
            "origin": "HKG",
            "destination": "Macau",
            "departure_time": "2026-05-01T04:00:00Z",
            "arrival_time": "2026-05-01T05:00:00Z",
            "carrier": "Citybus",
            "service_number": "A11",
            "vehicle_type": "bus",
            "status": "cancelled",
        },
        headers=headers,
    )
    assert transport.status_code == 201, transport.text
    return flight.json(), train.json(), transport.json()


def _list(client, headers, **params):
    response = client.get("/api/v1/records", params=params, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def test_unified_records_and_filters(client):
    token = register_and_login(client, "records_filters")["access_token"]
    headers = auth_headers(token)
    flight, train, transport = _create_records(client, headers)

    body = _list(client, headers)
    assert body["total"] == 3
    assert [item["id"] for item in body["items"]] == [
        transport["id"],
        train["id"],
        flight["id"],
    ]

    assert _list(client, headers, type="train")["items"][0]["id"] == train["id"]
    assert _list(client, headers, search="G100")["items"][0]["id"] == train["id"]
    assert _list(client, headers, status="cancelled")["items"][0]["id"] == transport["id"]
    assert _list(client, headers, carrier="Cathay")["items"][0]["id"] == flight["id"]

    body = _list(client, headers, date_from="2026-04-30", date_to="2026-04-30")
    assert [item["id"] for item in body["items"]] == [train["id"]]


def test_unified_records_trip_filter_and_sorting(client):
    token = register_and_login(client, "records_sort")["access_token"]
    headers = auth_headers(token)
    flight, train, transport = _create_records(client, headers)

    trip = client.post("/api/v1/trips", json={"name": "Records trip"}, headers=headers)
    assert trip.status_code == 201, trip.text
    response = client.patch(
        f"/api/v1/flights/{flight['id']}",
        json={"trip_id": trip.json()["id"]},
        headers=headers,
    )
    assert response.status_code == 200

    body = _list(client, headers, trip_id=trip.json()["id"])
    assert [item["id"] for item in body["items"]] == [flight["id"]]

    assert [item["id"] for item in _list(client, headers, sort="oldest")["items"]] == [
        flight["id"],
        train["id"],
        transport["id"],
    ]
    assert [item["id"] for item in _list(client, headers, sort="departure")["items"]] == [
        flight["id"],
        train["id"],
        transport["id"],
    ]
    assert [item["id"] for item in _list(client, headers, sort="arrival")["items"]] == [
        flight["id"],
        train["id"],
        transport["id"],
    ]
    assert [item["id"] for item in _list(client, headers, sort="created")["items"]] == [
        transport["id"],
        train["id"],
        flight["id"],
    ]


def test_unified_records_pagination(client):
    token = register_and_login(client, "records_pages")["access_token"]
    headers = auth_headers(token)
    _create_records(client, headers)

    first = _list(client, headers, page=1, page_size=2)
    assert first["total"] == 3
    assert len(first["items"]) == 2
    assert first["page"] == 1
    assert first["page_size"] == 2

    second = _list(client, headers, page=2, page_size=2)
    assert second["total"] == 3
    assert len(second["items"]) == 1


def test_unified_records_are_user_scoped(client):
    owner = register_and_login(client, "records_owner")["access_token"]
    other = register_and_login(client, "records_other")["access_token"]
    _create_records(client, auth_headers(owner))

    assert _list(client, auth_headers(other))["total"] == 0
