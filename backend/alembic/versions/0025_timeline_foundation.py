"""timeline foundation: ordering mode, activity timezone, expense source links

Revision ID: 0025
Revises: 0024
Create Date: 2026-11-06

Stage 0/1 of the record-model cleanup (docs/data-model.md):

- ``trips.timeline_order_mode`` decides whether the timeline is derived from
  event times (``chronological``) or from the stored order (``manual``).
  Existing trips become ``manual`` so their current order is preserved.
- ``activities.timezone`` records the display timezone of the event.
- ``expenses.source_*`` optionally links a spend to the record it paid for.
  The check constraint keeps the pair atomic.
- trip items identify one source entity per user, independent of the trip, so
  moving a record between trips keeps a single projection.
- idempotency keys prevent retried confirmations from creating duplicates.

The legacy ``trip_items.start_at/end_at`` columns are intentionally kept for
one more release: they still hold the only time of old place items and the
original values must stay auditable until stage 4 removes them.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0025"
down_revision: str | None = "0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()

    # -- trips.timeline_order_mode -----------------------------------------
    op.add_column(
        "trips",
        sa.Column(
            "timeline_order_mode",
            sa.String(length=20),
            nullable=False,
            server_default="manual",
        ),
    )
    # New trips are chronological; existing rows keep the value they were
    # backfilled with above.
    op.alter_column("trips", "timeline_order_mode", server_default="chronological")

    # -- activities.timezone ------------------------------------------------
    op.add_column("activities", sa.Column("timezone", sa.String(length=64), nullable=True))
    bind.execute(
        sa.text(
            """
            UPDATE activities
               SET timezone = (
                   SELECT places.timezone
                     FROM places
                    WHERE places.id = activities.place_id
               )
             WHERE timezone IS NULL
            """
        )
    )
    bind.execute(
        sa.text(
            """
            UPDATE activities
               SET timezone = (
                   SELECT users.timezone
                     FROM users
                    WHERE users.id = activities.user_id
               )
             WHERE timezone IS NULL
            """
        )
    )

    # -- expenses.source_type / source_id ----------------------------------
    op.add_column("expenses", sa.Column("source_type", sa.String(length=20), nullable=True))
    op.add_column("expenses", sa.Column("source_id", sa.Uuid(), nullable=True))
    op.create_check_constraint(
        "ck_expenses_source_pair",
        "expenses",
        "(source_type IS NULL AND source_id IS NULL) "
        "OR (source_type IS NOT NULL AND source_id IS NOT NULL)",
    )
    op.create_check_constraint(
        "ck_expenses_source_type",
        "expenses",
        "source_type IS NULL OR source_type IN ('transport', 'hotel', 'activity')",
    )
    op.create_index(
        "ix_expenses_source",
        "expenses",
        ["user_id", "source_type", "source_id"],
        unique=False,
    )
    op.create_index(
        "ix_expenses_user_trip",
        "expenses",
        ["user_id", "trip_id"],
        unique=False,
    )

    # -- one projection per source entity ----------------------------------
    # Never discard older projections here: a repeated place is a distinct
    # historical visit and its old row may be the only copy of its time.
    duplicate_rows = bind.execute(
        sa.text(
            """
            SELECT user_id, item_type, item_id
              FROM trip_items
             WHERE item_type <> 'place'
             GROUP BY user_id, item_type, item_id
            HAVING COUNT(*) > 1
            """
        )
    ).fetchall()
    if duplicate_rows:
        raise RuntimeError(
            "Duplicate timeline projections need explicit preservation and repair before "
            "migration 0025; no rows were deleted. Restore or retain the pre-switch backup."
        )
    # Place rows can represent multiple independent visits to the same place.
    # 0027 converts them first and only then creates the entity constraint.

    # -- idempotency keys ---------------------------------------------------
    op.create_table(
        "idempotency_keys",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("operation", sa.String(length=40), nullable=False),
        sa.Column("key", sa.String(length=120), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=True),
        sa.Column("response", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "operation",
            "key",
            name="uq_idempotency_keys_user_operation_key",
        ),
    )
    op.create_index("ix_idempotency_keys_user_id", "idempotency_keys", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_idempotency_keys_user_id", table_name="idempotency_keys")
    op.drop_table("idempotency_keys")

    if any(
        constraint["name"] == "uq_trip_items_user_entity"
        for constraint in sa.inspect(op.get_bind()).get_unique_constraints("trip_items")
    ):
        op.drop_constraint("uq_trip_items_user_entity", "trip_items", type_="unique")

    op.drop_index("ix_expenses_user_trip", table_name="expenses")
    op.drop_index("ix_expenses_source", table_name="expenses")
    op.drop_constraint("ck_expenses_source_type", "expenses", type_="check")
    op.drop_constraint("ck_expenses_source_pair", "expenses", type_="check")
    op.drop_column("expenses", "source_id")
    op.drop_column("expenses", "source_type")

    op.drop_column("activities", "timezone")

    op.alter_column("trips", "timeline_order_mode", server_default=None)
    op.drop_column("trips", "timeline_order_mode")
