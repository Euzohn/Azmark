# Reference Data Attribution

`airports.json` and `airlines.json` are generated offline and are **not** user
data. `airports.json` is the single source of truth the app loads at runtime —
it contains Chinese names too, composed from two stages.

```bash
./.venv/bin/python scripts/build_reference.py         # stage 1: base data
./.venv/bin/python scripts/build_airport_names_zh.py  # stage 2: fill Chinese names
```

## airports.json

Base data:

- Source: [OurAirports](https://ourairports.com/) data dump
  (`https://davidmegginson.github.io/ourairports-data/airports.csv`)
- License: **public domain**
- Filter: rows with a valid IATA code and type `large_airport` / `medium_airport` / `small_airport`

Chinese names (`name_zh` / `city_zh`) are filled in two ways:

1. A curated `AIRPORT_ZH` map inside `build_reference.py` (~100 major airports,
   including mainland-preferred names that differ from the local official name,
   e.g. LGK 兰卡威 vs the Malaysian 浮罗交怡).
2. The remaining fields are filled by `scripts/build_airport_names_zh.py` from
   [Wikidata](https://www.wikidata.org/) labels (`zh-hans`, falling back to `zh`)
   and P931 "place served" for the city.

- Wikidata license: **CC0 1.0 (public domain)**
- Wikidata `zh` labels are often Traditional (e.g. LGK only has
  "浮羅交怡國際機場"); the script converts every label to Simplified with
  `zhconv` so the zh-CN UI never shows 繁体字.
- An IATA code can belong to several Wikidata entities (a civil airport and a
  co-located military base, e.g. `ABQ`). The script keeps the entity whose
  English label best matches the `airports.json` name.

## airlines.json

- Source: [OpenFlights](https://github.com/jpatokal/openflights) `data/airlines.dat`
- License: **Open Database License (ODbL) 1.0**
- Filter: active airlines (`Active="Y"`) with a valid 2-character IATA code;
  controlled-duplicate IATA codes keep only the first (primary) holder

When modifying the filtering logic, update this file and re-run the scripts.
