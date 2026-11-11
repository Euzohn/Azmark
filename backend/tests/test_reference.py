import json
from pathlib import Path

import zhconv

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


def test_search_airports_by_chinese_name(client):
    """Chinese names merged from Wikidata must be searchable (spec #7)."""
    token = register_and_login(client, "ref_airport_zh_search")["access_token"]
    headers = auth_headers(token)

    # Full Chinese airport name
    response = client.get("/api/v1/reference/airports", params={"q": "遥墙"}, headers=headers)
    assert response.status_code == 200, response.text
    codes = [airport["iata"] for airport in response.json()]
    assert "TNA" in codes

    # Chinese city name
    response = client.get("/api/v1/reference/airports", params={"q": "济南"}, headers=headers)
    assert response.status_code == 200
    codes = [airport["iata"] for airport in response.json()]
    assert "TNA" in codes


def test_get_airport_by_iata_has_chinese_name(client):
    """A Chinese airport without a curated name_zh gets one from Wikidata."""
    token = register_and_login(client, "ref_airport_tna")["access_token"]
    response = client.get("/api/v1/reference/airports/TNA", headers=auth_headers(token))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["iata"] == "TNA"
    assert body["name_zh"] == "济南遥墙国际机场"


def test_airport_name_override_wins(client):
    """LGK's curated name is mainland 兰卡威, not the local official 浮罗交怡."""
    token = register_and_login(client, "ref_airport_lgk")["access_token"]
    response = client.get("/api/v1/reference/airports/LGK", headers=auth_headers(token))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["name_zh"] == "兰卡威国际机场"
    assert body["city_zh"] == "兰卡威"


def test_shipped_chinese_names_are_simplified():
    """Wikidata's `zh` labels are often Traditional; zh-CN must never show 繁体字.

    Whole-file guard so a regeneration cannot silently reintroduce Traditional
    characters for some airports.
    """
    path = Path(__file__).resolve().parent.parent / "app" / "data" / "airports.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    offenders = [
        (entry["iata"], field, value)
        for entry in data
        for field in ("name_zh", "city_zh")
        if (value := entry.get(field)) and zhconv.convert(value, "zh-hans") != value
    ]
    assert offenders == []


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


def test_normalize_station_name_variants():
    from app.services import reference

    # The trailing 站 / 火车站 marker is not part of the lookup identity.
    assert reference.normalize_station_name("上海虹桥站") == "上海虹桥"
    assert reference.normalize_station_name("北京南站") == "北京南"
    assert reference.normalize_station_name("  广州东  ") == "广州东"
    # Full-width and hyphenated forms fold together.
    assert reference.normalize_station_name("深圳北－") == "深圳北"
    # English suffixes are stripped; case and spaces fold.
    assert reference.normalize_station_name("Shanghai Hongqiao Railway Station") == (
        "shanghaihongqiao"
    )
    assert reference.normalize_station_name("SHANGHAI-HONGQIAO") == "shanghaihongqiao"
    assert reference.normalize_station_name("") == ""


def test_station_point_uses_registry_when_present():
    from app.services import reference

    registry = {"上海虹桥": {"name": "上海虹桥", "lat": 31.19598, "lon": 121.3162}}
    monkey = reference._stations_by_name
    reference._stations_by_name = lambda: registry
    try:
        point = reference.station_point("上海虹桥站")  # 站 suffix folded away
        assert point is not None
        assert point["precise"] is True
        assert point["lat"] == 31.19598
        assert point["lon"] == 121.3162
    finally:
        reference._stations_by_name = monkey


def test_station_point_registry_entry_gets_curated_city():
    from app.services import reference

    # stations.json has no city column, but the curated hub table fills it so
    # the map can group nearby stations under one city label at low zoom.
    registry = {"北京南": {"name": "北京南", "lat": 39.865, "lon": 116.378}}
    monkey = reference._stations_by_name
    reference._stations_by_name = lambda: registry
    try:
        point = reference.station_point("北京南")
        assert point is not None
        assert point["precise"] is True
        assert point["city"] == "北京"
    finally:
        reference._stations_by_name = monkey


def test_station_point_registry_entry_without_curated_city():
    from app.services import reference

    # An unknown station keeps city=None instead of guessing from its name.
    registry = {"某某北": {"name": "某某北", "lat": 38.9, "lon": 117.4}}
    monkey = reference._stations_by_name
    reference._stations_by_name = lambda: registry
    try:
        point = reference.station_point("某某北")
        assert point is not None
        assert point["precise"] is True
        assert point["city"] is None
    finally:
        reference._stations_by_name = monkey


def test_station_point_falls_back_to_city_coordinates():
    from app.services import reference

    # With no registry (stations.json absent) the curated station→city table and
    # the city coordinates from airports.json still place the station (spec #27).
    monkey = reference._stations_by_name
    reference._stations_by_name = lambda: {}
    try:
        point = reference.station_point("上海虹桥")
        assert point is not None
        assert point["precise"] is False
        assert point["city"] == "上海"
        assert 31.0 < point["lat"] < 31.4
        assert 121.2 < point["lon"] < 121.9

        hk = reference.station_point("香港西九龙")
        assert hk is not None
        assert hk["city"] == "香港"
    finally:
        reference._stations_by_name = monkey


def test_station_point_unknown_station_returns_none():
    from app.services import reference

    monkey = reference._stations_by_name
    reference._stations_by_name = lambda: {}
    try:
        assert reference.station_point("NoSuchStation") is None
        assert reference.station_point("") is None
    finally:
        reference._stations_by_name = monkey
