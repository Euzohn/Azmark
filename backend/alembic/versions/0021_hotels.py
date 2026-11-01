"""add hotels

Revision ID: 0021
Revises: 0020
Create Date: 2026-11-01

Spec #17: accommodation is its own entity, not a transport record. It is
date-based (check-in / check-out) and links into a trip through
``trip_items.item_type = 'hotel'``. The confirmation number is sensitive
(spec #45/#96) and stored encrypted.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0021"
down_revision: str | None = "0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "hotels",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("hotel", sa.String(length=160), nullable=False),
        sa.Column("check_in", sa.Date(), nullable=False),
        sa.Column("check_out", sa.Date(), nullable=True),
        sa.Column("room_type", sa.String(length=60), nullable=True),
        sa.Column("room_number", sa.String(length=20), nullable=True),
        sa.Column("booking_reference_enc", sa.Text(), nullable=True),
        sa.Column("price", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=True),
        sa.Column("address", sa.String(length=300), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "trip_id",
            sa.Uuid(),
            sa.ForeignKey("trips.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_hotels_user_id"), "hotels", ["user_id"], unique=False)
    op.create_index(op.f("ix_hotels_trip_id"), "hotels", ["trip_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_hotels_trip_id"), table_name="hotels")
    op.drop_index(op.f("ix_hotels_user_id"), table_name="hotels")
    op.drop_table("hotels")
