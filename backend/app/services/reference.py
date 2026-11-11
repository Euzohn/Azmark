"""Read-only reference data: airports (OurAirports + Wikidata) and airlines.

Loaded once into memory from the vendored JSON in `app/data/`. See
`app/data/ATTRIBUTION.md` and `scripts/build_reference.py` /
`scripts/build_airport_names_zh.py` for how the files are built.
"""

import json
import re
import unicodedata
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
    "北京朝阳": "北京",
    "北京丰台": "北京",
    "上海站": "上海",
    "上海南": "上海",
    "上海南站": "上海",
    "上海虹桥": "上海",
    "上海虹桥站": "上海",
    "上海西": "上海",
    "广州站": "广州",
    "广州南": "广州",
    "广州南站": "广州",
    "广州东": "广州",
    "广州东站": "广州",
    "广州北": "广州",
    "深圳站": "深圳",
    "深圳北": "深圳",
    "深圳北站": "深圳",
    "深圳东": "深圳",
    "深圳西": "深圳",
    "福田": "深圳",
    "杭州站": "杭州",
    "杭州东": "杭州",
    "杭州东站": "杭州",
    "杭州西": "杭州",
    "杭州南": "杭州",
    "南京站": "南京",
    "南京南": "南京",
    "南京南站": "南京",
    "南京北": "南京",
    "成都站": "成都",
    "成都东": "成都",
    "成都东站": "成都",
    "成都南": "成都",
    "成都西": "成都",
    "重庆北": "重庆",
    "重庆北站": "重庆",
    "重庆西": "重庆",
    "重庆西站": "重庆",
    "重庆东": "重庆",
    "沙坪坝": "重庆",
    "天津站": "天津",
    "天津南": "天津",
    "天津南站": "天津",
    "天津西": "天津",
    "天津西站": "天津",
    "天津北": "天津",
    "武汉站": "武汉",
    "武汉": "武汉",
    "汉口": "武汉",
    "武昌": "武汉",
    "西安站": "西安",
    "西安北": "西安",
    "西安南": "西安",
    "长沙站": "长沙",
    "长沙南": "长沙",
    "郑州站": "郑州",
    "郑州东": "郑州",
    "郑州西": "郑州",
    "济南站": "济南",
    "济南西": "济南",
    "济南东": "济南",
    "青岛站": "青岛",
    "青岛北": "青岛",
    "青岛西": "青岛",
    "沈阳站": "沈阳",
    "沈阳北": "沈阳",
    "沈阳南": "沈阳",
    "大连站": "大连",
    "大连北": "大连",
    "哈尔滨站": "哈尔滨",
    "哈尔滨西": "哈尔滨",
    "哈尔滨东": "哈尔滨",
    "长春站": "长春",
    "长春西": "长春",
    "石家庄站": "石家庄",
    "石家庄北": "石家庄",
    "石家庄东": "石家庄",
    "太原站": "太原",
    "太原南": "太原",
    "呼和浩特站": "呼和浩特",
    "呼和浩特东": "呼和浩特",
    "兰州站": "兰州",
    "兰州西": "兰州",
    "西宁站": "西宁",
    "银川站": "银川",
    "乌鲁木齐站": "乌鲁木齐",
    "乌鲁木齐南": "乌鲁木齐",
    "拉萨站": "拉萨",
    "昆明站": "昆明",
    "昆明南": "昆明",
    "贵阳站": "贵阳",
    "贵阳北": "贵阳",
    "贵阳东": "贵阳",
    "南宁站": "南宁",
    "南宁东": "南宁",
    "南宁西": "南宁",
    "海口站": "海口",
    "海口东": "海口",
    "三亚站": "三亚",
    "福州站": "福州",
    "福州南": "福州",
    "厦门站": "厦门",
    "厦门北": "厦门",
    "南昌站": "南昌",
    "南昌西": "南昌",
    "南昌东": "南昌",
    "合肥站": "合肥",
    "合肥南": "合肥",
    "宁波站": "宁波",
    "温州站": "温州",
    "温州南": "温州",
    "苏州站": "苏州",
    "苏州北": "苏州",
    "苏州园区": "苏州",
    "无锡站": "无锡",
    "无锡东": "无锡",
    "常州站": "常州",
    "常州北": "常州",
    "徐州站": "徐州",
    "徐州东": "徐州",
    "洛阳站": "洛阳",
    "洛阳龙门": "洛阳",
    "桂林站": "桂林",
    "桂林北": "桂林",
    "桂林西": "桂林",
}

# Station labels that resolve to a city for map coordinates only. Kept apart
# from _STATION_CITIES so place_city_key (statistics identity) stays untouched
# for regions outside mainland China.
_STATION_CITY_HINTS = {
    "香港西九龙": "香港",
    "香港红磡": "香港",
    "左营": "高雄",
    "台北": "台北",
    "台中": "台中",
    "台南": "台南",
    "新竹": "新竹",
    "嘉义": "嘉义",
    "桃园": "桃园",
    "基隆": "基隆",
    "花莲": "花莲",
    "台东": "台东",
}

_STATION_SUFFIXES = ("火车站", "站")
_EN_STATION_SUFFIX_RE = re.compile(r"(\s+(?:railway|train|high[- ]?speed)\s+station|\s+station)$")


def station_city_label(station_name: str) -> str:
    """Best-effort display city for a station, e.g. 上海虹桥 -> 上海 (spec #27).

    Purely presentational: statistics identity is *not* derived from this, so
    the HK/TW hints are safe to use here (see ``place_city_key``).
    """
    label = (station_name or "").strip()
    return (
        _STATION_CITIES.get(label)
        or _STATION_CITY_HINTS.get(label)
        or label.removesuffix("站").strip()
        or label
    )


def normalize_station_name(name: str) -> str:
    """Fold a user-entered station name into a lookup key.

    Handles the variations actually seen in records: full-width characters and
    separators, a trailing 「站」/「火车站」, English suffixes such as "Railway
    Station", and case. Simplified/traditional conversion is intentionally not
    performed at runtime (``zhconv`` stays a build-time dependency).
    """
    text = unicodedata.normalize("NFKC", name or "").casefold()
    text = re.sub(r"[\s\-_·.]+", " ", text).strip()
    text = _EN_STATION_SUFFIX_RE.sub("", text).strip()
    text = text.replace(" ", "")
    for suffix in _STATION_SUFFIXES:
        if text.endswith(suffix):
            text = text[: -len(suffix)]
            break
    return text.strip()


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


@lru_cache(maxsize=1)
def _stations() -> tuple[dict[str, Any], ...]:
    """Optional precise station coordinates.

    ``app/data/stations.json`` (mainland China) is produced by
    ``scripts/build_stations.py`` (OpenStreetMap, ODbL). It ships with the repo
    but stays **optional at runtime**: if the file is deleted, the map falls
    back to city-level coordinates. See ``app/data/ATTRIBUTION.md``.
    """
    path = DATA_DIR / "stations.json"
    if not path.exists():
        return ()
    with path.open(encoding="utf-8") as fh:
        return tuple(json.load(fh))


@lru_cache(maxsize=1)
def _stations_by_name() -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for station in _stations():
        labels = [station.get("name"), station.get("name_en"), station.get("name_zh")]
        alt = station.get("alt")
        if alt:
            labels.extend(part.strip() for part in alt.split(";"))
        for label in labels:
            if not label:
                continue
            key = normalize_station_name(label)
            if key and key not in index:
                index[key] = station
    return index


@lru_cache(maxsize=1)
def _city_coords() -> dict[str, tuple[float, float]]:
    """City-level fallback coordinates derived from the vendored airport data.

    A city's airports are averaged into one point. This is deliberately coarse:
    train routes on the map are schematic (spec #27), and a city-level endpoint
    beats not drawing the route at all when no station registry is present.
    """
    totals: dict[str, list[float]] = {}
    for airport in _airports():
        lat, lon = airport.get("lat"), airport.get("lon")
        if lat is None or lon is None:
            continue
        for label in (airport.get("city_zh"), airport.get("city")):
            if not label:
                continue
            key = label.strip().casefold()
            bucket = totals.setdefault(key, [0.0, 0.0, 0.0])
            bucket[0] += float(lat)
            bucket[1] += float(lon)
            bucket[2] += 1
    return {
        key: (round(values[0] / values[2], 6), round(values[1] / values[2], 6))
        for key, values in totals.items()
        if values[2]
    }


def _station_city(label: str) -> str | None:
    """Curated station→city lookup, tolerant of a trailing 「站」.

    Returns ``None`` when the station is not in the curated tables; callers
    then fall back to treating the label itself as a city.
    """
    for candidate in (label, label.removesuffix("站").strip()):
        city = _STATION_CITIES.get(candidate)
        if city:
            return city
    return _STATION_CITY_HINTS.get(label)


def station_point(name: str) -> dict[str, Any] | None:
    """Resolve a station name to a map point for schematic train routes.

    Order: precise ``stations.json`` entry (when the optional build script has
    been run) -> curated station-to-city table -> the name itself as a city.
    City coordinates come from ``airports.json``. Returns ``None`` when nothing
    can be resolved, in which case the record is left off the map.

    Precise registry entries carry no city field of their own, so the curated
    table still fills ``city`` for known hubs — the map groups nearby stations
    under one city label at low zoom levels.
    """
    label = (name or "").strip()
    if not label:
        return None
    key = normalize_station_name(label)
    station = _stations_by_name().get(key)
    if station:
        registry_name = station.get("name") or label
        return {
            "name": registry_name,
            "city": _station_city(registry_name) or _station_city(label),
            "lat": float(station["lat"]),
            "lon": float(station["lon"]),
            "precise": True,
        }

    city = _station_city(label)
    if city is None:
        city = label.removesuffix("站").strip()

    coords = _city_coords().get(city.casefold())
    if coords is None:
        return None
    return {
        "name": label,
        "city": city,
        "lat": coords[0],
        "lon": coords[1],
        "precise": False,
    }


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
