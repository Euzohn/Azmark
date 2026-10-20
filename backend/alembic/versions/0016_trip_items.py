"""add ordered trip items

Revision ID: 0016
Revises: 0015
Create Date: 2026-10-20

Trips previously only linked records through ``transport_records.trip_id``.
Spec #16 defines a TripItem table with explicit ordering and time bounds, so
create it and backfill one ``transport`` item per already-grouped record.
"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "trip_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "trip_id",
            sa.Uuid(),
            sa.ForeignKey("trips.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("item_type", sa.String(length=20), nullable=False),
        sa.Column("item_id", sa.Uuid(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("trip_id", "item_type", "item_id", name="uq_trip_items_trip_item"),
    )
    op.create_index(op.f("ix_trip_items_user_id"), "trip_items", ["user_id"], unique=False)
    op.create_index(op.f("ix_trip_items_trip_id"), "trip_items", ["trip_id"], unique=False)

    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            "SELECT id, user_id, trip_id, departure_time, arrival_time "
            "FROM transport_records "
            "WHERE trip_id IS NOT NULL "
            "ORDER BY trip_id, departure_time ASC NULLS LAST, created_at ASC"
        )
    ).fetchall()

    order_by_trip: dict[object, int] = {}
    for row in rows:
        sort_order = order_by_trip.get(row.trip_id, 0)
        order_by_trip[row.trip_id] = sort_order + 1
        bind.execute(
            sa.text(
                "INSERT INTO trip_items "
                "(id, user_id, trip_id, item_type, item_id, sort_order, start_at, end_at) "
                "VALUES (:id, :user_id, :trip_id, 'transport', :item_id, :sort_order, "
                ":start_at, :end_at)"
            ),
            {
                "id": uuid.uuid4(),
                "user_id": row.user_id,
                "trip_id": row.trip_id,
                "item_id": row.id,
                "sort_order": sort_order,
                "start_at": row.departure_time,
                "end_at": row.arrival_time,
            },
        )


def downgrade() -> None:
    op.drop_index(op.f("ix_trip_items_trip_id"), table_name="trip_items")
    op.drop_index(op.f("ix_trip_items_user_id"), table_name="trip_items")
    op.drop_table("trip_items")
