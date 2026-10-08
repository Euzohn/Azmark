"""Read-only reference data: airports (OurAirports) and airlines (OpenFlights).

Loaded once into memory from the vendored JSON in `app/data/`. See
`app/data/ATTRIBUTION.md` and `scripts/build_reference.py`.
"""

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

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
def _airlines_by_iata() -> dict[str, dict[str, Any]]:
    return {a["iata"]: a for a in _airlines()}


@lru_cache(maxsize=1)
def _airlines_by_icao() -> dict[str, dict[str, Any]]:
    return {a["icao"]: a for a in _airlines() if a.get("icao")}


def _airport_score(query: str, airport: dict[str, Any]) -> int | None:
    iata = airport["iata"].lower()
    city = (airport.get("city") or "").lower()
    name = airport["name"].lower()
    country = (airport.get("country") or "").lower()
    if iata == query:
        return 0
    if iata.startswith(query):
        return 1
    if city.startswith(query):
        return 2
    if name.startswith(query):
        return 3
    if query in city or query in name:
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
