"""Read-only reference data: airports (OurAirports + Wikidata) and airlines.

Loaded once into memory from the vendored JSON in `app/data/`. See
`app/data/ATTRIBUTION.md` and `scripts/build_reference.py` /
`scripts/build_airport_names_zh.py` for how the files are built.
"""

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# Explicit aliases only. Extend this list with verified station/city mappings;
# do not infer municipalities from arbitrary station name prefixes/suffixes.
_STATION_CITIES = {
    "北京站": "北京",
    "北京南": "北京",
    "北京南站": "北京",
    "北京西": "北京",
    "北京西站": "北京",
    "北京北": "北京",
    "北京北站": "北京",
    "上海站": "上海",
    "上海南": "上海",
    "上海南站": "上海",
    "上海虹桥": "上海",
    "上海虹桥站": "上海",
    "广州站": "广州",
    "广州南": "广州",
    "广州南站": "广州",
    "广州东": "广州",
    "广州东站": "广州",
    "深圳站": "深圳",
    "深圳北": "深圳",
    "深圳北站": "深圳",
    "杭州站": "杭州",
    "杭州东": "杭州",
    "杭州东站": "杭州",
    "南京站": "南京",
    "南京南": "南京",
    "南京南站": "南京",
    "成都站": "成都",
    "成都东": "成都",
    "成都东站": "成都",
    "重庆北": "重庆",
    "重庆北站": "重庆",
    "重庆西": "重庆",
    "重庆西站": "重庆",
    "天津站": "天津",
    "天津南": "天津",
    "天津南站": "天津",
    "天津西": "天津",
    "天津西站": "天津",
}


def airport_city_key(airport: dict[str, Any]) -> str:
    """Country-scoped identity; Chinese city labels also merge airport districts."""
    city = airport.get("city_zh") or airport.get("city") or ""
    return f"{airport.get('country') or ''}:{city.strip().casefold()}"


@lru_cache(maxsize=1)
def _city_aliases() -> dict[str, str]:
    candidates: dict[str, set[str]] = {}
    for airport in _airports():
        if not airport.get("city"):
            continue
        for label in (airport.get("city"), airport.get("city_zh")):
            if label:
                candidates.setdefault(label.strip().casefold(), set()).add(
                    airport_city_key(airport)
                )
    # Ambiguous city names must not silently merge places in different countries.
    return {label: next(iter(keys)) for label, keys in candidates.items() if len(keys) == 1}


def place_city_key(place: str) -> str:
    label = place.strip()
    city = _STATION_CITIES.get(label, label)
    # Curated station mappings refer to Chinese cities even if reference data
    # changes or the same translated name occurs abroad.
    if label in _STATION_CITIES:
        return f"CN:{city}"
    return _city_aliases().get(city.casefold(), f"place:{city.casefold()}")


_IATA_FLIGHT_RE = re.compile(r"^([A-Z0-9]{2})(\d{1,4})$")
_ICAO_FLIGHT_RE = re.compile(r"^([A-Z]{3})(\d{1,4})$")


@lru_cache(maxsize=1)
def _airports() -> tuple[dict[str, Any], ...]:
    with (DATA_DIR / "airports.json").open(encoding="utf-8") as fh:
        return tuple(json.load(fh))


@lru_cache(maxsize=1)
def _airlines() -> tuple[dict[str, Any], ...]:
    with (DATA_DIR / "airlines.json").open(encoding="utf-8") as fh:
        return tuple(json.load(fh))


@lru_cache(maxsize=1)
def _airports_by_iata() -> dict[str, dict[str, Any]]:
    return {a["iata"]: a for a in _airports()}


@lru_cache(maxsize=1)
def _airlines_by_iata() -> dict[str, dict[str, Any]]:
    return {a["iata"]: a for a in _airlines()}


@lru_cache(maxsize=1)
def _airlines_by_icao() -> dict[str, dict[str, Any]]:
    return {a["icao"]: a for a in _airlines() if a.get("icao")}


def _airport_score(query: str, airport: dict[str, Any]) -> int | None:
    iata = airport["iata"].lower()
    city = (airport.get("city") or "").lower()
    name = airport["name"].lower()
    city_zh = (airport.get("city_zh") or "").lower()
    name_zh = (airport.get("name_zh") or "").lower()
    country = (airport.get("country") or "").lower()
    if iata == query:
        return 0
    if iata.startswith(query):
        return 1
    if city.startswith(query) or city_zh.startswith(query):
        return 2
    if name.startswith(query) or name_zh.startswith(query):
        return 3
    if query in city or query in name or query in city_zh or query in name_zh:
        return 4
    if country == query:
        return 5
    return None


def search_airports(query: str, *, limit: int = 10) -> list[dict[str, Any]]:
    q = query.strip().lower()
    if not q:
        return []
    scored: list[tuple[int, str, dict[str, Any]]] = []
    for airport in _airports():
        score = _airport_score(q, airport)
        if score is not None:
            scored.append((score, airport["name"], airport))
    scored.sort(key=lambda item: (item[0], item[1]))
    return [airport for _, _, airport in scored[:limit]]


def _airline_score(query: str, airline: dict[str, Any]) -> int | None:
    iata = airline["iata"].lower()
    icao = (airline.get("icao") or "").lower()
    name = airline["name"].lower()
    country = (airline.get("country") or "").lower()
    if iata == query or icao == query:
        return 0
    if iata.startswith(query) or icao.startswith(query):
        return 1
    if name.startswith(query):
        return 2
    if query in name:
        return 3
    if country == query:
        return 4
    return None


def search_airlines(query: str, *, limit: int = 10) -> list[dict[str, Any]]:
    q = query.strip().lower()
    if not q:
        return []
    scored: list[tuple[int, str, dict[str, Any]]] = []
    for airline in _airlines():
        score = _airline_score(q, airline)
        if score is not None:
            scored.append((score, airline["name"], airline))
    scored.sort(key=lambda item: (item[0], item[1]))
    return [airline for _, _, airline in scored[:limit]]


def get_airline_by_iata(iata: str) -> dict[str, Any] | None:
    """Resolve a single airline by its IATA code (e.g. 'CX')."""
    return _airlines_by_iata().get(iata)


def get_airport_by_iata(iata: str) -> dict[str, Any] | None:
    """Resolve a single airport by its IATA code (e.g. 'HKG')."""
    return _airports_by_iata().get(iata)


def normalize_flight_number(number: str) -> str:
    return re.sub(r"[\s-]", "", number).upper()


def lookup_flight_number(number: str) -> dict[str, Any]:
    """Resolve a flight number to its operating airline by code prefix (spec #38).

    Only the airline is inferred locally. Route/times/aircraft require an
    external FlightProvider (a keyed or live-only source) and are out of scope.
    """
    normalized = normalize_flight_number(number)
    digital = _IATA_FLIGHT_RE.match(normalized)
    if digital:
        code = digital.group(1)
        airline = _airlines_by_iata().get(code)
    else:
        three = _ICAO_FLIGHT_RE.match(normalized)
        code = three.group(1) if three else None
        airline = _airlines_by_icao().get(code) if code else None
    return {"flight_number": normalized, "airline_code": code, "airline": airline}
