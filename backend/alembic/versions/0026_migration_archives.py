"""migration archives and place→visit mappings

Revision ID: 0026
Revises: 0025
Create Date: 2026-11-06

Stage 2 prerequisite (docs/data-model.md §10.2). These tables only preserve
migration evidence so a legacy place item can be traced back after the
conversion. They are user-scoped, never read by the timeline, and deliberately
keep historical UUIDs without foreign keys to the business records.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0026"
down_revision: str | None = "0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "timeline_migration_archives",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("migration_key", sa.String(length=64), nullable=False),
        sa.Column("original_item_id", sa.Uuid(), nullable=False),
        sa.Column("trip_id", sa.Uuid(), nullable=True),
        sa.Column("item_type", sa.String(length=20), nullable=False),
        sa.Column("item_id", sa.Uuid(), nullable=True),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("source_start_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_end_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("diff_type", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("user_choice", sa.String(length=40), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "migration_key",
            "original_item_id",
            name="uq_timeline_archives_user_key_item",
        ),
    )
    op.create_index(
        "ix_timeline_migration_archives_user_id",
        "timeline_migration_archives",
        ["user_id"],
        unique=False,
    )

    op.create_table(
        "place_visit_mappings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("migration_key", sa.String(length=64), nullable=False),
        sa.Column("original_item_id", sa.Uuid(), nullable=False),
        sa.Column("activity_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "migration_key",
            "original_item_id",
            name="uq_place_visit_mappings_user_key_item",
        ),
    )
    op.create_index(
        "ix_place_visit_mappings_user_id",
        "place_visit_mappings",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_place_visit_mappings_user_id", table_name="place_visit_mappings")
    op.drop_table("place_visit_mappings")
    op.drop_index(
        "ix_timeline_migration_archives_user_id",
        table_name="timeline_migration_archives",
    )
    op.drop_table("timeline_migration_archives")
