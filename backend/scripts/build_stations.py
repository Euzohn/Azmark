"""Build app/data/stations.json from OpenStreetMap railway stations (spec #27).

The map draws schematic train routes between the origin and destination stations.
Flights resolve their endpoints through ``airports.json`` (IATA -> coordinates);
trains need the same kind of lookup, which OSM provides. Only the names and the
coordinates are kept — this is reference data, not user data.

- Source: OpenStreetMap via the Overpass API, license **ODbL 1.0**
  (see ``app/data/ATTRIBUTION.md``).
- Filter: ``railway=station`` nodes that carry a name and are not subway /
  light-rail / tram / monorail stations (they share the same tag) and are not
  disused, abandoned, proposed or under construction.
- Scope: CN / HK / MO / TW by default; ``--countries`` widens or narrows it.

Run from backend/ (network required):

    ./.venv/bin/python scripts/build_stations.py
    ./.venv/bin/python scripts/build_stations.py --countries CN,HK
    HTTPS_PROXY=http://127.0.0.1:7897 ./.venv/bin/python scripts/build_stations.py

``urllib`` honours the standard ``http_proxy`` / ``https_proxy`` environment
variables, which is how the script runs behind a local proxy. The public
Overpass instance rejects requests without a descriptive User-Agent, so one is
sent explicitly.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

from build_reference import write_json_records

DATA_DIR = Path(__file__).resolve().parent.parent / "app" / "data"
STATIONS = DATA_DIR / "stations.json"
ENDPOINT = "https://overpass-api.de/api/interpreter"
USER_AGENT = "Azmark-reference-builder (+https://github.com/)"
RETRIES = 4
RETRY_WAIT_SECONDS = 20

# ``railway=station`` is also used for metro/tram stops in some regions; those
# are useless for intercity rail routes, so they are dropped here.
NON_RAIL_STATION_TYPES = {
    "subway",
    "light_rail",
    "tram",
    "monorail",
    "funicular",
    "disused",
    "abandoned",
    "proposed",
    "construction",
}

QUERY = """
[out:json][timeout:{timeout}];
area["ISO3166-1"="{iso}"]["admin_level"="2"]->.a;
node(area.a)["railway"="station"];
out body;
"""

BBOX_QUERY = """
[out:json][timeout:{timeout}];
node["railway"="station"]({south},{west},{north},{east});
out body;
"""

# Area lookups for small territories are heavy for the public instance and fail
# with 502/504 under load. Their bounding boxes are tight enough to use directly
# as a fallback: no neighbouring country's stations fall inside them.
BBOX_FALLBACK: dict[str, tuple[float, float, float, float]] = {
    # south, west, north, east
    "HK": (22.15, 113.82, 22.57, 114.44),
    "MO": (22.10, 113.52, 22.22, 113.60),
    "TW": (21.85, 118.15, 25.35, 122.05),
}


def fetch_country(iso: str, *, timeout: int) -> list[dict]:
    """Return the raw Overpass elements for one country, with retries.

    The area query is retried first. When it keeps failing and a country has a
    tight bounding box configured, the bbox query is used instead.
    """
    queries = [QUERY.format(iso=iso, timeout=timeout)]
    if iso in BBOX_FALLBACK:
        south, west, north, east = BBOX_FALLBACK[iso]
        queries.append(
            BBOX_QUERY.format(timeout=timeout, south=south, west=west, north=north, east=east)
        )
    for query in queries:
        elements = _fetch(query, iso=iso, timeout=timeout)
        # An empty result counts as a failed lookup: the area for a small
        # territory may be missing, and 0 stations must not pass as "complete".
        if elements:
            return elements
        print(f"  {iso}: query returned no nodes", file=sys.stderr)
    return []


def _fetch(query: str, *, iso: str, timeout: int) -> list[dict] | None:
    body = urllib.parse.urlencode({"data": query}).encode()
    for attempt in range(1, RETRIES + 1):
        request = urllib.request.Request(
            ENDPOINT,
            data=body,
            headers={"User-Agent": USER_AGENT, "Content-Type": "application/x-www-form-urlencoded"},
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout + 60) as response:
                payload = json.load(response)
            return payload.get("elements", [])
        except Exception as exc:  # noqa: BLE001 - network errors are retried wholesale
            if attempt == RETRIES:
                print(f"  {iso}: {exc!r}; giving up on this query", file=sys.stderr)
                return None
            wait = RETRY_WAIT_SECONDS * attempt
            print(
                f"  {iso}: {exc!r}; retry {attempt}/{RETRIES - 1} in {wait}s",
                file=sys.stderr,
            )
            time.sleep(wait)
    return None


def station_record(element: dict) -> dict | None:
    """Turn one Overpass node into a compact station record, or ``None``."""
    tags = element.get("tags") or {}
    name = (tags.get("name") or "").strip()
    if not name:
        return None
    if tags.get("station") in NON_RAIL_STATION_TYPES:
        return None
    if tags.get("subway") == "yes":
        return None
    if tags.get("disused") == "yes" or tags.get("railway:historic"):
        return None
    lat, lon = element.get("lat"), element.get("lon")
    if lat is None or lon is None:
        return None

    record = {
        "name": name,
        "lat": round(float(lat), 5),
        "lon": round(float(lon), 5),
    }
    name_en = (tags.get("name:en") or "").strip()
    if name_en and name_en != name:
        record["name_en"] = name_en
    name_zh = (tags.get("name:zh") or tags.get("name:zh-Hans") or "").strip()
    if name_zh and name_zh != name:
        record["name_zh"] = name_zh
    alt = (tags.get("alt_name") or "").strip()
    if alt:
        record["alt"] = alt
    return record


def build_stations(countries: list[str], *, timeout: int) -> list[dict]:
    seen: set[tuple[str, float, float]] = set()
    stations: list[dict] = []
    for iso in countries:
        print(f"Querying {iso} railway stations", file=sys.stderr)
        elements = fetch_country(iso, timeout=timeout)
        kept = 0
        for element in elements:
            record = station_record(element)
            if record is None:
                continue
            # The same station can be mapped twice (node + platform); keep one.
            key = (record["name"], record["lat"], record["lon"])
            if key in seen:
                continue
            seen.add(key)
            stations.append(record)
            kept += 1
        print(f"  {iso}: {kept} stations kept of {len(elements)} nodes", file=sys.stderr)

    stations.sort(key=lambda item: (item["name"], item.get("name_en") or ""))
    return stations


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--countries",
        default="CN,HK,MO,TW",
        help="Comma-separated ISO 3166-1 alpha-2 codes (default: CN,HK,MO,TW).",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=180,
        help="Overpass query timeout in seconds (default: 180).",
    )
    args = parser.parse_args()

    countries = [code.strip().upper() for code in args.countries.split(",") if code.strip()]
    stations = build_stations(countries, timeout=args.timeout)
    if not stations:
        print("no stations fetched — refusing to overwrite stations.json", file=sys.stderr)
        return 1

    write_json_records(STATIONS, stations)
    print(
        f"wrote {STATIONS} ({STATIONS.stat().st_size} bytes, {len(stations)} stations)",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
