from tests.conftest import auth_headers, register_and_login


def test_search_airports_by_iata(client):
    token = register_and_login(client, "ref_air")["access_token"]
    response = client.get(
        "/api/v1/reference/airports", params={"q": "HKG"}, headers=auth_headers(token)
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body[0]["iata"] == "HKG"
    assert body[0]["name"] == "Hong Kong International Airport"


def test_search_airports_by_city(client):
    token = register_and_login(client, "ref_city")["access_token"]
    response = client.get(
        "/api/v1/reference/airports", params={"q": "singapore"}, headers=auth_headers(token)
    )
    assert response.status_code == 200
    codes = [airport["iata"] for airport in response.json()]
    assert "SIN" in codes


def test_search_airlines(client):
    token = register_and_login(client, "ref_airline")["access_token"]
    response = client.get(
        "/api/v1/reference/airlines", params={"q": "cathay"}, headers=auth_headers(token)
    )
    assert response.status_code == 200
    body = response.json()[0]
    assert body["iata"] == "CX"
    assert body["name"] == "Cathay Pacific"
    assert body["name_zh"] == "国泰航空"


def test_airline_name_override(client):
    """OpenFlights is stale for some carriers; overrides must win (spec: Scoot)."""
    token = register_and_login(client, "ref_override")["access_token"]
    headers = auth_headers(token)

    response = client.get("/api/v1/reference/airlines/TR", headers=headers)
    assert response.status_code == 200
    assert response.json()["name"] == "Scoot"

    response = client.get("/api/v1/reference/airlines/AZ", headers=headers)
    assert response.status_code == 200
    assert response.json()["name"] == "ITA Airways"


def test_search_airports_include_zh_names(client):
    token = register_and_login(client, "ref_airport_zh")["access_token"]
    response = client.get(
        "/api/v1/reference/airports", params={"q": "HKG"}, headers=auth_headers(token)
    )
    assert response.status_code == 200
    body = response.json()[0]
    assert body["name_zh"] == "香港国际机场"
    assert body["city_zh"] == "香港"


def test_flight_number_lookup(client):
    token = register_and_login(client, "ref_flight")["access_token"]
    response = client.get(
        "/api/v1/reference/flight-lookup", params={"number": "CX659"}, headers=auth_headers(token)
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["airline_code"] == "CX"
    assert body["airline"]["name"] == "Cathay Pacific"


def test_flight_number_lookup_unknown_airline(client):
    token = register_and_login(client, "ref_unknown")["access_token"]
    response = client.get(
        "/api/v1/reference/flight-lookup", params={"number": "QQQ123"}, headers=auth_headers(token)
    )
    assert response.status_code == 200
    assert response.json()["airline"] is None


def test_reference_requires_auth(client):
    assert client.get("/api/v1/reference/airports", params={"q": "HKG"}).status_code == 401
    assert client.get("/api/v1/reference/airlines", params={"q": "CX"}).status_code == 401
    assert (
        client.get("/api/v1/reference/flight-lookup", params={"number": "CX659"}).status_code == 401
    )
