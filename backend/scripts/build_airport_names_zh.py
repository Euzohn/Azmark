"""Fetch Chinese airport names from Wikidata into app/data/airport_names_zh.json.

OurAirports only ships English names, and `build_reference.py`'s curated
``AIRPORT_ZH`` covers a few dozen major airports. This script fills the rest
from Wikidata labels (CC0), preferring simplified Chinese (``zh-hans``) and
falling back to ``zh``.

An IATA code is not unique in Wikidata: a civil airport and a co-located
military base can share the same code, with conflicting labels (e.g. ``ABQ``
maps to both "Albuquerque International Sunport" and "Kirtland Air Force
Base"). To pick the right entity we compare Wikidata's English label against
the airport name in `airports.json` and keep the best-matching entity's labels
and place-served (P931) city. The runtime merges this file over `airports.json`
in `app.services.reference`, so `airports.json` stays exactly what the upstream
builder produced.

Run from backend/:
    ./.venv/bin/python scripts/build_airport_names_zh.py
    ./.venv/bin/python scripts/build_airport_names_zh.py --countries CN,HK,MO,TW
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "app" / "data"
OUTPUT = DATA_DIR / "airport_names_zh.json"
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
    usable = sorted({value.strip() for value in values if value and CJK_RE.search(value)})
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--countries",
        default="",
        help="Comma-separated ISO country codes to limit the fetch (default: all).",
    )
    parser.add_argument(
        "--keep-existing",
        action="store_true",
        help="Merge into the current airport_names_zh.json instead of replacing it.",
    )
    args = parser.parse_args()

    with (DATA_DIR / "airports.json").open(encoding="utf-8") as fh:
        airports = json.load(fh)

    allowed = {code.strip().upper() for code in args.countries.split(",") if code.strip()}
    codes_by_name = {
        airport["iata"]: airport["name"]
        for airport in airports
        if not allowed or airport["country"] in allowed
    }
    print(f"Querying Wikidata for {len(codes_by_name)} airports", file=sys.stderr)
    fetched = fetch_names(codes_by_name)

    if args.keep_existing and OUTPUT.exists():
        with OUTPUT.open(encoding="utf-8") as fh:
            existing = json.load(fh)
        existing.update(fetched)
        fetched = existing

    with OUTPUT.open("w", encoding="utf-8") as fh:
        json.dump(fetched, fh, ensure_ascii=False, indent=1, sort_keys=True)
        fh.write("\n")

    print(
        f"Wrote {len(fetched)} Chinese airport names to {OUTPUT} "
        f"({OUTPUT.stat().st_size // 1024} KB)",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
