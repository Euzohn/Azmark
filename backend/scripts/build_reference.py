"""Regenerate app/data/{airports,airlines}.json from public datasets.

Sources (downloaded into memory, only filtered JSON is written to disk):
- OurAirports airports.csv (public domain): https://davidmegginson.github.io/ourairports-data/airports.csv
- OpenFlights airlines.dat (ODbL 1.0): https://raw.githubusercontent.com/jpatokal/openflights/master/data/airlines.dat

Run from backend/:
    ./.venv/bin/python scripts/build_reference.py
"""

import csv
import io
import json
import re
import sys
import urllib.request
from pathlib import Path

AIRPORTS_URL = "https://davidmegginson.github.io/ourairports-data/airports.csv"
AIRLINES_URL = "https://raw.githubusercontent.com/jpatokal/openflights/master/data/airlines.dat"

DATA_DIR = Path(__file__).resolve().parent.parent / "app" / "data"

AIRPORT_TYPES = {"large_airport", "medium_airport", "small_airport"}
IATA_RE = re.compile(r"^[A-Z0-9]{3}$")
AIRLINE_IATA_RE = re.compile(r"^[A-Z0-9]{2}$")
USER_AGENT = "Azmark-reference-builder (+https://github.com/)"


def fetch(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def clean(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


def build_airports() -> list[dict]:
    rows = csv.DictReader(io.StringIO(fetch(AIRPORTS_URL)))
    by_iata: dict[str, dict] = {}
    skipped_type = 0
    skipped_code = 0
    for row in rows:
        iata = (row.get("iata_code") or "").strip().upper()
        if not IATA_RE.match(iata):
            skipped_code += 1
            continue
        if row.get("type") not in AIRPORT_TYPES:
            skipped_type += 1
            continue
        if iata in by_iata:
            continue
        icao = (row.get("gps_code") or "").strip().upper()
        try:
            lat = float(row["latitude_deg"])
            lon = float(row["longitude_deg"])
        except (KeyError, ValueError):
            continue
        by_iata[iata] = {
            "iata": iata,
            "icao": icao if re.match(r"^[A-Z0-9]{4}$", icao) else None,
            "name": (row.get("name") or "").strip(),
            "city": clean(row.get("municipality")),
            "country": clean(row.get("iso_country")),
            "lat": round(lat, 6),
            "lon": round(lon, 6),
        }
    airports = sorted(by_iata.values(), key=lambda a: a["iata"])
    print(
        f"airports: {len(airports)} kept, {skipped_type} without scheduled-service type, "
        f"{skipped_code} without valid IATA"
    )
    return airports


def build_airlines() -> list[dict]:
    rows = csv.reader(io.StringIO(fetch(AIRLINES_URL)))
    by_iata: dict[str, dict] = {}
    for fields in rows:
        if len(fields) < 8:
            continue
        _id, name, _alias, iata, icao, _callsign, country, active = (
            field.strip() for field in fields[:8]
        )
        iata = iata.upper()
        if active != "Y" or not AIRLINE_IATA_RE.match(iata):
            continue
        if not name or name.startswith("(") or name.lower().startswith("unnamed"):
            continue
        if iata in by_iata:
            continue  # controlled duplicates: keep the first (primary) holder
        icao = icao.upper()
        by_iata[iata] = {
            "iata": iata,
            "icao": icao if re.match(r"^[A-Z0-9]{3}$", icao) else None,
            "name": name,
            "country": clean(country),
        }
    airlines = sorted(by_iata.values(), key=lambda a: a["iata"])
    print(f"airlines: {len(airlines)} kept (active with IATA)")
    return airlines


def main() -> int:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    outputs = {
        "airports.json": build_airports,
        "airlines.json": build_airlines,
    }
    for filename, builder in outputs.items():
        data = builder()
        path = DATA_DIR / filename
        path.write_text(
            json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        print(
            f"wrote {path.relative_to(DATA_DIR.parent.parent)} ({path.stat().st_size} bytes, "
            f"{len(data)} entries)"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
