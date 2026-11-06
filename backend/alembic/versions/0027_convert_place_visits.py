"""convert legacy place trip items into visit activities

Revision ID: 0027
Revises: 0026
Create Date: 2026-11-06

Stage 2 data migration (docs/data-model.md §10.3). Every legacy
``trip_items.item_type='place'`` becomes an Activity with ``type='visit'``:

- the original Activity name is a snapshot of the Place name;
- the legacy item id, sort order and visit window are preserved;
- the trip item is converted in place to ``item_type='activity'``;
- a mapping row and a timeline archive row record the old state.

The migration never merges visits by similarity: two trips to the same place
remain two events. Invalid, missing or cross-user references and inverted
windows block conversion so they can be repaired without losing history.

After the conversion the database forbids ``item_type='place'``.
Downgrade only relaxes the constraint; reverting converted rows is unsafe after
new writes, so restore a pre-switch backup instead (docs §10.5).
"""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op

revision: str = "0027"
down_revision: str | None = "0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

MIGRATION_KEY = "0027_place_visit"


def upgrade() -> None:
    bind = op.get_bind()
    rows = (
        bind.execute(
            sa.text(
                """
                SELECT ti.id AS item_id,
                       ti.user_id,
                       ti.trip_id,
                       ti.item_id AS place_id,
                       ti.start_at,
                       ti.end_at,
                       ti.sort_order,
                       places.name AS place_name,
                       places.timezone AS place_timezone,
                       users.timezone AS user_timezone,
                       trips.id AS valid_trip_id
                  FROM trip_items AS ti
                  LEFT JOIN places
                         ON places.id = ti.item_id
                        AND places.user_id = ti.user_id
                  LEFT JOIN users
                         ON users.id = ti.user_id
                  LEFT JOIN trips
                         ON trips.id = ti.trip_id
                        AND trips.user_id = ti.user_id
                 WHERE ti.item_type = 'place'
                 ORDER BY ti.user_id, ti.trip_id, ti.sort_order, ti.id
                """
            )
        )
        .mappings()
        .all()
    )

    if any(
        row["place_name"] is None
        or row["valid_trip_id"] is None
        or (row["start_at"] and row["end_at"] and row["end_at"] < row["start_at"])
        for row in rows
    ):
        raise RuntimeError("Invalid legacy place references or time windows; repair before 0027")

    now = datetime.now(UTC)
    for row in rows:
        activity_id = uuid.uuid4()
        place_exists = row["place_name"] is not None
        trip_exists = row["valid_trip_id"] is not None

        # Preserve the event even when its references are broken; the archive
        # below records what was missing rather than dropping the row.
        bind.execute(
            sa.text(
                """
                INSERT INTO activities (
                    id, user_id, name, type, place_id, start_at, end_at,
                    timezone, trip_id, created_at, updated_at
                ) VALUES (
                    :id, :user_id, :name, 'visit', :place_id, :start_at, :end_at,
                    :timezone, :trip_id, :created_at, :updated_at
                )
                """
            ),
            {
                "id": activity_id,
                "user_id": row["user_id"],
                "name": row["place_name"] or "Visit",
                "place_id": row["place_id"] if place_exists else None,
                "start_at": row["start_at"],
                "end_at": row["end_at"],
                "timezone": row["place_timezone"] or row["user_timezone"],
                "trip_id": row["valid_trip_id"] if trip_exists else None,
                "created_at": now,
                "updated_at": now,
            },
        )

        bind.execute(
            sa.text(
                """
                UPDATE trip_items
                   SET item_type = 'activity',
                       item_id = :activity_id,
                       start_at = NULL,
                       end_at = NULL
                 WHERE id = :item_id
                """
            ),
            {"activity_id": activity_id, "item_id": row["item_id"]},
        )

        bind.execute(
            sa.text(
                """
                INSERT INTO place_visit_mappings (
                    id, user_id, migration_key, original_item_id, activity_id,
                    created_at
                ) VALUES (
                    :id, :user_id, :migration_key, :original_item_id, :activity_id,
                    :created_at
                )
                """
            ),
            {
                "id": uuid.uuid4(),
                "user_id": row["user_id"],
                "migration_key": MIGRATION_KEY,
                "original_item_id": row["item_id"],
                "activity_id": activity_id,
                "created_at": now,
            },
        )

        if not place_exists:
            diff_type, status = "missing_place", "converted_without_place"
        elif not trip_exists:
            diff_type, status = "missing_trip", "converted_without_trip"
        else:
            diff_type, status = "place_to_visit", "converted"

        bind.execute(
            sa.text(
                """
                INSERT INTO timeline_migration_archives (
                    id, user_id, migration_key, original_item_id, trip_id,
                    item_type, item_id, start_at, end_at, sort_order,
                    source_start_at, source_end_at, diff_type, status,
                    user_choice, created_at
                ) VALUES (
                    :id, :user_id, :migration_key, :original_item_id, :trip_id,
                    'place', :place_id, :start_at, :end_at, :sort_order,
                    NULL, NULL, :diff_type, :status, 'created_visit', :created_at
                )
                """
            ),
            {
                "id": uuid.uuid4(),
                "user_id": row["user_id"],
                "migration_key": MIGRATION_KEY,
                "original_item_id": row["item_id"],
                "trip_id": row["trip_id"],
                "place_id": row["place_id"],
                "start_at": row["start_at"],
                "end_at": row["end_at"],
                "sort_order": row["sort_order"],
                "diff_type": diff_type,
                "status": status,
                "created_at": now,
            },
        )

    if not any(
        constraint["name"] == "uq_trip_items_user_entity"
        for constraint in sa.inspect(bind).get_unique_constraints("trip_items")
    ):
        op.create_unique_constraint(
            "uq_trip_items_user_entity", "trip_items", ["user_id", "item_type", "item_id"]
        )

    op.create_check_constraint(
        "ck_trip_items_item_type",
        "trip_items",
        "item_type IN ('transport', 'hotel', 'activity')",
    )


def downgrade() -> None:
    raise RuntimeError(
        "Place items were converted to visit Activities; restore the pre-switch "
        "backup instead of downgrading this data migration."
    )
