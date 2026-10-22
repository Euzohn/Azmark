# Reference Data Attribution

`airports.json` and `airlines.json` are generated offline by
`scripts/build_reference.py` and are **not** user data. Regenerate with:

```bash
./.venv/bin/python scripts/build_reference.py
```

## airports.json

- Source: [OurAirports](https://ourairports.com/) data dump
  (`https://davidmegginson.github.io/ourairports-data/airports.csv`)
- License: **public domain**
- Filter: rows with a valid IATA code and type `large_airport` / `medium_airport` / `small_airport`

## airlines.json

- Source: [OpenFlights](https://github.com/jpatokal/openflights) `data/airlines.dat`
- License: **Open Database License (ODbL) 1.0**
- Filter: active airlines (`Active="Y"`) with a valid 2-character IATA code;
  controlled-duplicate IATA codes keep only the first (primary) holder

When modifying the filtering logic, update this file and re-run the script.

## airport_names_zh.json

Chinese airport and city names not bundled by OurAirports. Generated offline by
`scripts/build_airport_names_zh.py` and merged over `airports.json` at runtime in
`app.services.reference` (only filling fields the upstream data left empty).

- Source: [Wikidata](https://www.wikidata.org/) labels (`zh-hans`, falling back
  to `zh`) and P931 "place served" for the city
- License: **CC0 1.0 (public domain)**
- Disambiguation: an IATA code can belong to several Wikidata entities (e.g. a
  civil airport and a co-located military base). The script keeps the entity
  whose English label best matches the `airports.json` name.
