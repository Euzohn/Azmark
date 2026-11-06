"""Exercise destructive migration guards without a running database service."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, text


@pytest.fixture
def migration(monkeypatch):
    path = Path(__file__).parents[1] / "alembic/versions/0029_drop_trip_item_times.py"
    spec = importlib.util.spec_from_file_location("migration_0029_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        for ddl in (
            "CREATE TABLE trips (id TEXT, user_id TEXT)",
            "CREATE TABLE transport_records (id TEXT, user_id TEXT, trip_id TEXT, "
            "departure_time TEXT, arrival_time TEXT)",
            "CREATE TABLE hotels (id TEXT, user_id TEXT, trip_id TEXT, "
            "check_in TEXT, check_out TEXT)",
            "CREATE TABLE activities (id TEXT, user_id TEXT, trip_id TEXT, "
            "start_at TEXT, end_at TEXT)",
            "CREATE TABLE trip_items (id TEXT, user_id TEXT, trip_id TEXT, item_type TEXT, "
            "item_id TEXT, start_at TEXT, end_at TEXT, sort_order INTEGER)",
            "CREATE TABLE timeline_migration_archives (user_id TEXT, original_item_id TEXT, "
            "trip_id TEXT, item_type TEXT, item_id TEXT, start_at TEXT, end_at TEXT, "
            "sort_order INTEGER, status TEXT, user_choice TEXT, source_start_at TEXT, "
            "source_end_at TEXT, migration_key TEXT)",
            "CREATE TABLE place_visit_mappings (user_id TEXT, original_item_id TEXT, "
            "activity_id TEXT, migration_key TEXT)",
        ):
            conn.execute(text(ddl))
        conn.execute(text("INSERT INTO trips VALUES ('t', 'u')"))
        conn.execute(text("INSERT INTO transport_records VALUES ('s', 'u', 't', NULL, NULL)"))
        conn.execute(
            text("INSERT INTO trip_items VALUES ('i', 'u', 't', 'transport', 's', NULL, NULL, 0)")
        )
        conn.execute(
            text(
                "INSERT INTO timeline_migration_archives VALUES "
                "('u', 'i', 't', 'transport', 's', NULL, NULL, 0, 'resolved', 'keep_source', "
                "NULL, NULL, 'audit')"
            )
        )
        dropped = []
        monkeypatch.setattr(
            module,
            "op",
            SimpleNamespace(get_bind=lambda: conn, drop_column=lambda *a: dropped.append(a)),
        )
        yield module, conn, dropped
    engine.dispose()


@pytest.mark.parametrize(
    "mutation",
    [
        "DELETE FROM transport_records",
        "UPDATE transport_records SET user_id = 'other'",
        "UPDATE transport_records SET trip_id = 'other'",
        "UPDATE trips SET user_id = 'other'",
        "DELETE FROM trip_items",
        "UPDATE timeline_migration_archives SET item_type = 'hotel'",
        "UPDATE timeline_migration_archives SET item_id = 'other'",
        "UPDATE timeline_migration_archives SET trip_id = 'other'",
        "UPDATE timeline_migration_archives SET user_choice = 'created_visit'",
        "UPDATE timeline_migration_archives SET status = 'converted'",
        "UPDATE transport_records SET departure_time = '2026-01-01 00:00:00'",
        "UPDATE timeline_migration_archives SET source_start_at = '2026-01-01 00:00:00'",
    ],
)
def test_blocks_invalid_data_before_dropping_columns(migration, mutation):
    module, conn, dropped = migration
    conn.execute(text(mutation))
    with pytest.raises(RuntimeError, match="0029 blocked"):
        module.upgrade()
    assert dropped == []


def test_valid_data_allows_drop(migration):
    module, _, dropped = migration
    module.upgrade()
    assert dropped == [("trip_items", "end_at"), ("trip_items", "start_at")]


def test_use_item_requires_source_to_reflect_selection(migration):
    module, conn, dropped = migration
    conn.execute(text("UPDATE trip_items SET start_at = '2026-01-01 10:00:00'"))
    conn.execute(
        text(
            "UPDATE timeline_migration_archives SET start_at = '2026-01-01 10:00:00', "
            "user_choice = 'use_item'"
        )
    )
    with pytest.raises(RuntimeError, match="0029 blocked"):
        module.upgrade()
    assert dropped == []
    conn.execute(text("UPDATE transport_records SET departure_time = '2026-01-01 10:00:00'"))
    module.upgrade()
    assert len(dropped) == 2


def test_converted_place_requires_mapping(migration):
    module, conn, dropped = migration
    conn.execute(text("DELETE FROM transport_records"))
    conn.execute(text("INSERT INTO activities VALUES ('s', 'u', 't', NULL, NULL)"))
    conn.execute(text("UPDATE trip_items SET item_type = 'activity'"))
    conn.execute(
        text(
            "UPDATE timeline_migration_archives SET item_type = 'place', item_id = 'p', "
            "status = 'converted', user_choice = 'created_visit'"
        )
    )
    with pytest.raises(RuntimeError, match="0029 blocked"):
        module.upgrade()
    assert dropped == []
    conn.execute(text("INSERT INTO place_visit_mappings VALUES ('u', 'i', 's', 'audit')"))
    module.upgrade()
    assert len(dropped) == 2
