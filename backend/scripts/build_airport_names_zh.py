"""Fill Chinese airport names in app/data/airports.json from Wikidata.

`build_reference.py` builds `airports.json` from OurAirports (English only) plus
a small curated `AIRPORT_ZH` map. This script is the second stage of that build:
it fetches Chinese labels (CC0) from Wikidata and writes them back into
`airports.json`, filling only the `name_zh` / `city_zh` fields the curated map
left empty. There is no separate supplement file — `airports.json` is the single
source of truth the app loads at runtime.

- Wikidata's ``zh`` label is often Traditional (LGK only has
  "浮羅交怡國際機場", with no ``zh-hans``). Every label is run through
  ``zhconv`` so the zh-CN UI never shows 繁体字 — a global conversion, not a
  per-airport fix.
- An IATA code is not unique in Wikidata: a civil airport and a co-located
  military base can share a code (e.g. ``ABQ``). The best entity is chosen by
  matching Wikidata's English label against the `airports.json` name.
- Mainland-preferred names that differ from the local official name (e.g. LGK
  兰卡威 vs 浮罗交怡) belong in `build_reference.py`'s curated ``AIRPORT_ZH``
  map, not here.

Run from backend/ (after `build_reference.py`):
    ./.venv/bin/python scripts/build_airport_names_zh.py
    ./.venv/bin/python scripts/build_airport_names_zh.py --countries CN,HK,MO,TW
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

import zhconv
from build_reference import write_json_records

DATA_DIR = Path(__file__).resolve().parent.parent / "app" / "data"
AIRPORTS = DATA_DIR / "airports.json"
ENDPOINT = "https://query.wikidata.org/sparql"
USER_AGENT = "Azmark-reference-builder (+https://github.com/)"
CHUNK_SIZE = 250
RETRIES = 3

CJK_RE = re.compile(r"[\u3400-\u9fff]")
NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")

QUERY = """
SELECT ?iata ?airport ?en ?hans ?zh ?cityHans ?cityZh WHERE {
  VALUES ?iata { %s }
  ?airport wdt:P238 ?iata .
  OPTIONAL { ?airport rdfs:label ?en FILTER(LANG(?en) = "en") }
  OPTIONAL { ?airport rdfs:label ?hans FILTER(LANG(?hans) = "zh-hans") }
  OPTIONAL { ?airport rdfs:label ?zh FILTER(LANG(?zh) = "zh") }
  OPTIONAL {
    ?airport wdt:P931 ?city .
    ?city rdfs:label ?cityHans FILTER(LANG(?cityHans) = "zh-hans")
  }
  OPTIONAL {
    ?airport wdt:P931 ?otherCity .
    ?otherCity rdfs:label ?cityZh FILTER(LANG(?cityZh) = "zh")
  }
}
"""


def fetch(query: str) -> dict:
    url = f"{ENDPOINT}?" + urllib.parse.urlencode({"query": query, "format": "json"})
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    last_error: Exception | None = None
    for attempt in range(1, RETRIES + 1):
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                return json.load(response)
        except Exception as exc:  # noqa: BLE001 - retried below
            last_error = exc
            if attempt < RETRIES:
                time.sleep(2 * attempt)
    raise RuntimeError(f"Wikidata query failed: {last_error}") from last_error


def _normalise(value: str) -> str:
    return NON_ALNUM_RE.sub("", value.lower())


def _similarity(our_name: str, en_label: str | None) -> int:
    """Token-overlap score between our airport name and a Wikidata en label."""
    if not en_label:
        return -1
    ours = _normalise(our_name)
    candidate = _normalise(en_label)
    if not candidate:
        return -1
    if ours == candidate:
        return 1000
    if ours.startswith(candidate) or candidate.startswith(ours):
        return 100
    ours_tokens = {token for token in re.split(r"[^a-z0-9]+", our_name.lower()) if token}
    candidate_tokens = {token for token in re.split(r"[^a-z0-9]+", en_label.lower()) if token}
    overlap = len(ours_tokens & candidate_tokens)
    return overlap


def _first_cjk(values: set[str]) -> str | None:
    simplified = {
        zhconv.convert(value.strip(), "zh-hans")
        for value in values
        if value and CJK_RE.search(value)
    }
    usable = sorted(value for value in simplified if value and CJK_RE.search(value))
    if not usable:
        return None
    return min(usable, key=len)


def _pick_entity(rows: list[dict], our_name: str) -> dict:
    """Group a code's bindings by Wikidata entity and keep the best match."""
    entities: dict[str, dict[str, set]] = {}
    for row in rows:
        entity = row["airport"]["value"]
        keys = ("en", "hans", "zh", "cityHans", "cityZh")
        store = entities.setdefault(entity, {key: set() for key in keys})
        for key in ("en", "hans", "zh", "cityHans", "cityZh"):
            value = row.get(key, {}).get("value")
            if value:
                store[key].add(value)

    best_score = -2
    best: dict | None = None
    for store in entities.values():
        en_label = next(iter(store["en"]), None) if store["en"] else None
        score = _similarity(our_name, en_label)
        # Prefer entities that have a Chinese label at all over those without.
        if not (store["hans"] or store["zh"]):
            score -= 1
        if score > best_score:
            best_score = score
            best = store
    return best or {"hans": set(), "zh": set(), "cityHans": set(), "cityZh": set()}


def fetch_names(codes_by_name: dict[str, str]) -> dict[str, dict[str, str]]:
    codes = list(codes_by_name)
    result: dict[str, dict[str, str]] = {}
    for start in range(0, len(codes), CHUNK_SIZE):
        chunk = codes[start : start + CHUNK_SIZE]
        values = " ".join(f'"{code}"' for code in chunk)
        payload = fetch(QUERY % values)
        grouped: dict[str, list[dict]] = {}
        for binding in payload["results"]["bindings"]:
            grouped.setdefault(binding["iata"]["value"], []).append(binding)
        for code in chunk:
            our_name = codes_by_name[code]
            chosen = _pick_entity(grouped.get(code, []), our_name)
            name = _first_cjk(chosen["hans"]) or _first_cjk(chosen["zh"])
            city = _first_cjk(chosen["cityHans"]) or _first_cjk(chosen["cityZh"])
            if name and city and name in city:
                city = None
            entry = {key: value for key, value in (("name_zh", name), ("city_zh", city)) if value}
            if entry:
                result[code] = entry
        done = min(start + CHUNK_SIZE, len(codes))
        print(f"  {done}/{len(codes)} codes queried", file=sys.stderr)
        time.sleep(0.3)
    return result


def apply(airports: list[dict], fetched: dict[str, dict[str, str]]) -> tuple[int, int]:
    """Fill empty name_zh/city_zh; return (airports filled, fields filled)."""
    filled_airports = 0
    filled_fields = 0
    for airport in airports:
        fill = fetched.get(airport["iata"])
        if not fill:
            continue
        changed = False
        for field in ("name_zh", "city_zh"):
            if not airport.get(field) and fill.get(field):
                airport[field] = fill[field]
                filled_fields += 1
                changed = True
        if changed:
            filled_airports += 1
    return filled_airports, filled_fields


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--countries",
        default="",
        help="Comma-separated ISO country codes to limit the fetch (default: all).",
    )
    args = parser.parse_args()

    with AIRPORTS.open(encoding="utf-8") as fh:
        airports = json.load(fh)

    allowed = {code.strip().upper() for code in args.countries.split(",") if code.strip()}
    codes_by_name = {
        airport["iata"]: airport["name"]
        for airport in airports
        if not allowed or airport["country"] in allowed
    }
    print(f"Querying Wikidata for {len(codes_by_name)} airports", file=sys.stderr)
    fetched = fetch_names(codes_by_name)

    filled_airports, filled_fields = apply(airports, fetched)

    tmp = AIRPORTS.with_suffix(".json.tmp")
    write_json_records(tmp, airports)
    os.replace(tmp, AIRPORTS)
    print(
        f"wrote {AIRPORTS} ({AIRPORTS.stat().st_size} bytes) — "
        f"filled {filled_fields} fields across {filled_airports} airports",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
