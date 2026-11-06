"""drop legacy trip item time columns

Revision ID: 0029
Revises: 0028
Create Date: 2026-11-06

Stage 4 cleanup (docs/data-model.md §10.5). Event times are owned by Transport,
Hotel and Activity; ``trip_items`` is now only a stable projection id plus the
manual order. 0026 creates the archive table and 0027 archives place rows;
other rows must be explicitly audited and archived before this column drop.

The downgrade only recreates empty nullable columns: the old values cannot be
reconstructed from the projection, so a real rollback must restore the
pre-switch backup.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0029"
down_revision: str | None = "0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    # A projection must point at an existing source belonging to the same
    # user and trip, and every trip member must have exactly one projection.
    invalid = bind.execute(
        sa.text(
            """
            SELECT COUNT(*) FROM trip_items ti
            WHERE NOT EXISTS (
                SELECT 1 FROM trips t WHERE t.id = ti.trip_id AND t.user_id = ti.user_id
            ) OR NOT (
                (ti.item_type = 'transport' AND EXISTS (
                    SELECT 1 FROM transport_records s WHERE s.id = ti.item_id
                    AND s.user_id = ti.user_id AND s.trip_id = ti.trip_id)) OR
                (ti.item_type = 'hotel' AND EXISTS (
                    SELECT 1 FROM hotels s WHERE s.id = ti.item_id
                    AND s.user_id = ti.user_id AND s.trip_id = ti.trip_id)) OR
                (ti.item_type = 'activity' AND EXISTS (
                    SELECT 1 FROM activities s WHERE s.id = ti.item_id
                    AND s.user_id = ti.user_id AND s.trip_id = ti.trip_id))
            )
            """
        )
    ).scalar_one()
    if invalid:
        raise RuntimeError(f"0029 blocked: {invalid} invalid timeline projections")
    for table, item_type in (
        ("transport_records", "transport"),
        ("hotels", "hotel"),
        ("activities", "activity"),
    ):
        # Table names are fixed migration constants, not user input.
        missing_projection = bind.execute(
            sa.text(
                f"SELECT COUNT(*) FROM {table} s WHERE s.trip_id IS NOT NULL "
                "AND NOT EXISTS (SELECT 1 FROM trip_items ti "
                "WHERE ti.user_id = s.user_id AND ti.trip_id = s.trip_id "
                "AND ti.item_type = :item_type AND ti.item_id = s.id)"
            ),
            {"item_type": item_type},
        ).scalar_one()
        if missing_projection:
            raise RuntimeError(
                f"0029 blocked: {missing_projection} missing {item_type} projections"
            )
    # The archive must exist *before* destructive DDL. 0026 only creates the
    # table and 0027 archives place rows; neither archives other legacy rows.
    # Verify that the selected historical values are actually reflected by the
    # source. Hotel dates were represented by UTC midnight in the old timeline.
    if bind.dialect.name == "sqlite":
        hotel_start = "datetime(h.check_in)"
        hotel_end = "datetime(h.check_out)"
    else:
        hotel_start = "(CAST(h.check_in AS timestamp) AT TIME ZONE 'UTC')"
        hotel_end = "(CAST(h.check_out AS timestamp) AT TIME ZONE 'UTC')"
    missing = bind.execute(
        sa.text(
            f"""
            SELECT count(*) FROM trip_items ti
            WHERE NOT EXISTS (
                SELECT 1 FROM timeline_migration_archives a
                WHERE a.user_id = ti.user_id AND a.original_item_id = ti.id
                  AND (
                      (a.item_type = ti.item_type AND a.item_id = ti.item_id
                       AND a.trip_id = ti.trip_id AND a.status = 'resolved'
                       AND a.user_choice IN ('keep_source', 'use_item')
                       AND a.start_at IS NOT DISTINCT FROM ti.start_at
                       AND a.end_at IS NOT DISTINCT FROM ti.end_at
                       AND (
                           (ti.item_type = 'transport' AND EXISTS (
                               SELECT 1 FROM transport_records s
                               WHERE s.id = ti.item_id AND s.user_id = ti.user_id
                               AND s.departure_time IS NOT DISTINCT FROM
                                   CASE WHEN a.user_choice = 'use_item' THEN a.start_at
                                        ELSE a.source_start_at END
                               AND s.arrival_time IS NOT DISTINCT FROM
                                   CASE WHEN a.user_choice = 'use_item' THEN a.end_at
                                        ELSE a.source_end_at END)) OR
                           (ti.item_type = 'activity' AND EXISTS (
                               SELECT 1 FROM activities s
                               WHERE s.id = ti.item_id AND s.user_id = ti.user_id
                               AND s.start_at IS NOT DISTINCT FROM
                                   CASE WHEN a.user_choice = 'use_item' THEN a.start_at
                                        ELSE a.source_start_at END
                               AND s.end_at IS NOT DISTINCT FROM
                                   CASE WHEN a.user_choice = 'use_item' THEN a.end_at
                                        ELSE a.source_end_at END)) OR
                           (ti.item_type = 'hotel' AND EXISTS (
                               SELECT 1 FROM hotels h
                               WHERE h.id = ti.item_id AND h.user_id = ti.user_id
                               AND {hotel_start} IS NOT DISTINCT FROM
                                   CASE WHEN a.user_choice = 'use_item' THEN a.start_at
                                        ELSE a.source_start_at END
                               AND {hotel_end} IS NOT DISTINCT FROM
                                   CASE WHEN a.user_choice = 'use_item' THEN a.end_at
                                        ELSE a.source_end_at END))
                       ))
                       OR (a.item_type = 'place' AND ti.item_type = 'activity'
                          AND a.trip_id = ti.trip_id AND a.status = 'converted'
                          AND a.user_choice = 'created_visit'
                          AND EXISTS (SELECT 1 FROM place_visit_mappings m
                              WHERE m.user_id = ti.user_id AND m.original_item_id = ti.id
                                AND m.activity_id = ti.item_id
                                AND m.migration_key = a.migration_key)
                          AND EXISTS (SELECT 1 FROM activities act
                              WHERE act.id = ti.item_id AND act.user_id = ti.user_id
                                AND act.start_at IS NOT DISTINCT FROM a.start_at
                                AND act.end_at IS NOT DISTINCT FROM a.end_at))
                  )
                  AND a.sort_order = ti.sort_order
            )
            """
        )
    ).scalar_one()
    if missing:
        raise RuntimeError(
            f"0029 blocked: {missing} trip items have no resolved matching archive. "
            "Audit and resolve historical times and order before dropping columns."
        )
    op.drop_column("trip_items", "end_at")
    op.drop_column("trip_items", "start_at")


def downgrade() -> None:
    op.add_column("trip_items", sa.Column("start_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("trip_items", sa.Column("end_at", sa.DateTime(timezone=True), nullable=True))
