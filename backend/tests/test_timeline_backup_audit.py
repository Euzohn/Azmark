"""The backup audit compares timestamps without logging record contents."""

import importlib.util
import io
import re
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "timeline_backup_audit", Path(__file__).parents[2] / "scripts/audit_timeline_backup.py"
)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def test_read_backup_accepts_0028_and_extracts_only_required_fields(monkeypatch):
    dump = (
        "COPY public.alembic_version (version_num) FROM stdin;\n0028\n\\.\n"
        "COPY public.trip_items (id, user_id, trip_id, item_type, item_id, "
        "start_at, end_at, secret) FROM stdin;\n"
        "i\tu\tt\ttransport\ts\t2026-01-01 00:00:00+00\t\\N\tprivate\n\\.\n"
        "COPY public.transport_records (id, user_id, trip_id, "
        "departure_time, arrival_time) FROM stdin;\n"
        "s\tu\tt\t2026-01-01 00:00:00+00\t\\N\n\\.\n"
        "COPY public.hotels (id, user_id, trip_id, check_in, check_out) FROM stdin;\n\\.\n"
        "COPY public.activities (id, user_id, trip_id, start_at, end_at) FROM stdin;\n\\.\n"
    )
    monkeypatch.setattr(audit.gzip, "open", lambda *args, **kwargs: io.StringIO(dump))
    tables = audit.read_backup("unused")
    assert "secret" not in tables["trip_items"][0]
    assert audit.compare(tables, set()) == {("transport", "match"): 1}


def test_backup_audit_compares_utc_instants_and_hotel_dates():
    null = r"\N"
    items = [
        {
            "id": "1",
            "user_id": "u",
            "trip_id": "t",
            "item_type": "transport",
            "item_id": "a",
            "start_at": "2026-01-01 10:00:00+08",
            "end_at": null,
        },
        {
            "id": "2",
            "user_id": "u",
            "trip_id": "t",
            "item_type": "hotel",
            "item_id": "b",
            "start_at": "2026-01-02 00:00:00+00",
            "end_at": null,
        },
        {
            "id": "3",
            "user_id": "u",
            "trip_id": "t",
            "item_type": "activity",
            "item_id": "c",
            "start_at": "2026-01-02 10:00:00+00",
            "end_at": null,
        },
        {
            "id": "4",
            "user_id": "u",
            "trip_id": "t",
            "item_type": "activity",
            "item_id": "missing",
            "start_at": "2026-01-02 10:00:00+00",
            "end_at": null,
        },
    ]
    tables = {
        "trip_items": items,
        "transport_records": [
            {
                "id": "a",
                "user_id": "u",
                "trip_id": "t",
                "departure_time": "2026-01-01 02:00:00+00",
                "arrival_time": null,
            }
        ],
        "hotels": [
            {"id": "b", "user_id": "u", "trip_id": "t", "check_in": "2026-01-02", "check_out": null}
        ],
        "activities": [
            {
                "id": "c",
                "user_id": "u",
                "trip_id": "t",
                "start_at": "2026-01-02 11:00:00+00",
                "end_at": null,
            }
        ],
    }
    counts = audit.compare(tables, {("u", "2")})
    assert counts == {
        ("transport", "match"): 1,
        ("activity", "different"): 1,
        ("activity", "missing_or_wrong_trip"): 1,
    }
    assert audit.compare(tables, set())[("hotel", "match")] == 1


def test_postgres_offsets_work_with_older_python(monkeypatch):
    original = audit.dt.datetime

    class OlderDatetime(original):
        @classmethod
        def fromisoformat(cls, value):
            if re.search(r"[+-]\d{2}$", value) or value.endswith("Z"):
                raise ValueError("unsupported by older Python")
            return super().fromisoformat(value)

    monkeypatch.setattr(audit.dt, "datetime", OlderDatetime)
    assert audit.instant("2026-01-01 10:00:00+08") == audit.instant("2026-01-01 02:00:00Z")
    assert audit.instant("2026-01-02", hotel_date=True) == audit.instant("2026-01-02 00:00:00+00")
