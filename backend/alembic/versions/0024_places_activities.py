"""add places and activities

Revision ID: 0024
Revises: 0023
Create Date: 2026-11-06

Spec #14 and #18: P1 adds user-scoped places and activities. A place is a
geo reference with no trip membership of its own — it joins a trip only
through an explicit ``trip_items`` row (``item_type='place'``). An activity
is a trip member like transport and hotels: ``trip_id`` mirrors into
``trip_items`` so it slots into the trip timeline at its ``start_at``.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0024"
down_revision: str | None = "0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "places",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("type", sa.String(length=20), nullable=False),
        sa.Column("country", sa.String(length=120), nullable=True),
        sa.Column("region", sa.String(length=120), nullable=True),
        sa.Column("city", sa.String(length=120), nullable=True),
        sa.Column("district", sa.String(length=120), nullable=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("localized_name", sa.String(length=200), nullable=True),
        sa.Column("lat", sa.Float(), nullable=True),
        sa.Column("lon", sa.Float(), nullable=True),
        sa.Column("timezone", sa.String(length=64), nullable=True),
        sa.Column("external_ids", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_places_user_id"), "places", ["user_id"], unique=False)

    op.create_table(
        "activities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("type", sa.String(length=40), nullable=False),
        sa.Column(
            "place_id",
            sa.Uuid(),
            sa.ForeignKey("places.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("price", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "trip_id",
            sa.Uuid(),
            sa.ForeignKey("trips.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_activities_user_id"), "activities", ["user_id"], unique=False)
    op.create_index(op.f("ix_activities_place_id"), "activities", ["place_id"], unique=False)
    op.create_index(op.f("ix_activities_trip_id"), "activities", ["trip_id"], unique=False)
    op.create_index(op.f("ix_activities_start_at"), "activities", ["start_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_activities_start_at"), table_name="activities")
    op.drop_index(op.f("ix_activities_trip_id"), table_name="activities")
    op.drop_index(op.f("ix_activities_place_id"), table_name="activities")
    op.drop_index(op.f("ix_activities_user_id"), table_name="activities")
    op.drop_table("activities")

    op.drop_index(op.f("ix_places_user_id"), table_name="places")
    op.drop_table("places")
