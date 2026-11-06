#!/usr/bin/env python3
"""Compare legacy timeline times with their sources in a 0028 pg_dump.

Read-only: no database restore, modifications, temporary files, or record values
in output. Current archive keys are queried through docker compose.
"""

import argparse
import collections
import datetime as dt
import gzip
import re
import subprocess
import sys

FIELDS = {
    "trip_items": {"id", "user_id", "trip_id", "item_type", "item_id", "start_at", "end_at"},
    "transport_records": {"id", "user_id", "trip_id", "departure_time", "arrival_time"},
    "hotels": {"id", "user_id", "trip_id", "check_in", "check_out"},
    "activities": {"id", "user_id", "trip_id", "start_at", "end_at"},
}
COPY = re.compile(r'^COPY (?:public\.)?"?(\w+)"? \((.*?)\) FROM stdin;')


def read_backup(path):
    tables = {name: [] for name in FIELDS}
    found = set()
    version = None
    with gzip.open(path, "rt", encoding="utf-8", errors="strict") as stream:
        for line in stream:
            match = COPY.match(line)
            if match and match.group(1) == "alembic_version":
                columns = [column.strip('" ') for column in match.group(2).split(",")]
                if columns != ["version_num"]:
                    raise ValueError("unexpected alembic version columns")
                version = next(stream, "").strip()
                continue
            if not match or match.group(1) not in FIELDS:
                continue
            name = match.group(1)
            columns = [column.strip('" ') for column in match.group(2).split(",")]
            if not FIELDS[name].issubset(columns):
                raise ValueError(f"missing required columns in {name}")
            indexes = {column: columns.index(column) for column in FIELDS[name]}
            found.add(name)
            for row in stream:
                if row.rstrip("\n") == r"\.":
                    break
                values = row.rstrip("\n").split("\t")
                if len(values) != len(columns):
                    raise ValueError(f"invalid COPY row in {name}")
                tables[name].append({key: values[index] for key, index in indexes.items()})
            else:
                raise ValueError(f"incomplete COPY section in {name}")
    if found != set(FIELDS):
        raise ValueError("backup is missing a required COPY section")
    if version != "0028":
        raise ValueError("backup is not at migration 0028")
    return tables


def instant(value, *, hotel_date=False):
    if value == r"\N":
        return None
    if hotel_date:
        return dt.datetime.combine(
            dt.date.fromisoformat(value),
            dt.time.min,
            tzinfo=dt.timezone.utc,  # noqa: UP017
        )
    # PostgreSQL commonly emits offsets like +00; Python before 3.11 requires
    # the full +00:00 form for datetime.fromisoformat().
    value = re.sub(r"([+-]\d{2})$", r"\1:00", value)
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    result = dt.datetime.fromisoformat(value)
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError("naive timestamp")
    return result.astimezone(dt.timezone.utc)  # noqa: UP017


def compare(tables, archived):
    sources = {
        name: {(row["user_id"], row["id"]): row for row in tables[name]}
        for name in ("transport_records", "hotels", "activities")
    }
    kinds = {
        "transport": ("transport_records", "departure_time", "arrival_time", False),
        "hotel": ("hotels", "check_in", "check_out", True),
        "activity": ("activities", "start_at", "end_at", False),
    }
    results = collections.Counter()
    for item in tables["trip_items"]:
        if (item["user_id"], item["id"]) in archived:
            continue
        if item["start_at"] == r"\N" and item["end_at"] == r"\N":
            continue
        kind = item["item_type"]
        if kind not in kinds:
            results[("unknown", "unknown_type")] += 1
            continue
        table, start, end, hotel_date = kinds[kind]
        source = sources[table].get((item["user_id"], item["item_id"]))
        if source is None or source["trip_id"] != item["trip_id"]:
            results[(kind, "missing_or_wrong_trip")] += 1
            continue
        try:
            old = (instant(item["start_at"]), instant(item["end_at"]))
            actual = (
                instant(source[start], hotel_date=hotel_date),
                instant(source[end], hotel_date=hotel_date),
            )
        except (ValueError, OverflowError):
            results[(kind, "invalid_time")] += 1
            continue
        results[(kind, "match" if old == actual else "different")] += 1
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("backup", help="0028 PostgreSQL plain-text .sql.gz backup")
    args = parser.parse_args()
    try:
        tables = read_backup(args.backup)
        result = subprocess.run(
            [
                "docker",
                "compose",
                "exec",
                "-T",
                "postgres",
                "psql",
                "-U",
                "azmark",
                "-d",
                "azmark",
                "-XAt",
                "-F",
                "\t",
                "-c",
                "SELECT user_id, original_item_id FROM timeline_migration_archives",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        archived = {tuple(line.split("\t")) for line in result.stdout.splitlines() if line}
        counts = compare(tables, archived)
    except (OSError, EOFError, UnicodeError, ValueError, subprocess.CalledProcessError) as exc:
        print(
            f"Audit failed: {type(exc).__name__}; check backup and database access", file=sys.stderr
        )
        return 1
    print("Unarchived 0028 rows with legacy times:", sum(counts.values()))
    for (kind, status), count in sorted(counts.items()):
        print(f"{kind} {status}: {count}")
    print("Comparison is against the backup snapshot, not necessarily the later migration state.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
