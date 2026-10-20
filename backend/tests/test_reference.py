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
    assert body["alliance"] == "oneworld"


def test_airline_alliance_field(client):
    token = register_and_login(client, "ref_alliance")["access_token"]
    headers = auth_headers(token)

    sq = client.get("/api/v1/reference/airlines/SQ", headers=headers)
    assert sq.status_code == 200
    assert sq.json()["alliance"] == "star_alliance"

    af = client.get("/api/v1/reference/airlines/AF", headers=headers)
    assert af.status_code == 200
    assert af.json()["alliance"] == "skyteam"

    tr = client.get("/api/v1/reference/airlines/TR", headers=headers)
    assert tr.status_code == 200
    assert tr.json()["alliance"] is None


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


def test_flight_number_lookup_y8_suparna(client):
    """Y8 is Jinpeng / Suparna; OpenFlights mislabels it, overrides must win."""
    token = register_and_login(client, "ref_y8")["access_token"]
    response = client.get(
        "/api/v1/reference/flight-lookup",
        params={"number": "Y87525"},
        headers=auth_headers(token),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["airline_code"] == "Y8"
    airline = body["airline"]
    assert airline["name"] == "Suparna Airlines"
    assert airline["name_zh"] == "金鹏航空"
    assert airline["icao"] == "YZR"
    assert airline["country"] == "China"


def test_flight_number_lookup_chinese_carriers_fixed(client):
    """OpenFlights mislabeled many CN carrier IATA codes as defunct/foreign
    airlines, and a few were missing entirely; overrides must restore the
    correct Chinese carrier (verified against IATA/lawnwing/Wikipedia)."""
    cases = [
        ("PN6201", "PN", "West Air", "西部航空"),  # 西部航空 — was "West Air China"
        ("TV9821", "TV", "Tibet Airlines", "西藏航空"),  # was Belgium Virgin Express
        ("JD5101", "JD", "Beijing Capital Airlines", "首都航空"),  # was Japan Air System
        ("GS7651", "GS", "Tianjin Airlines", "天津航空"),  # was UK Air Foyle
        ("DZ6231", "DZ", "Donghai Airlines", "东海航空"),  # was Kazakhstan Starline
        ("O36231", "O3", "SF Airlines", "顺丰航空"),  # was missing entirely
    ]
    token = register_and_login(client, "ref_cn")["access_token"]
    headers = auth_headers(token)
    for number, code, name, name_zh in cases:
        response = client.get(
            "/api/v1/reference/flight-lookup",
            params={"number": number},
            headers=headers,
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["airline_code"] == code, number
        airline = body["airline"]
        assert airline is not None, number
        assert airline["name"] == name, number
        assert airline["name_zh"] == name_zh, number
        assert airline["country"] == "China", number


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
