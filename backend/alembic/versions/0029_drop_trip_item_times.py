"""drop legacy trip item time columns

Revision ID: 0029
Revises: 0028
Create Date: 2026-11-06

Stage 4 cleanup (docs/data-model.md §10.5). Event times are owned by Transport,
Hotel and Activity; ``trip_items`` is now only a stable projection id plus the
manual order. The original values were archived by migration 0026/0027 in
``timeline_migration_archives`` before this column drop.

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
    op.drop_column("trip_items", "end_at")
    op.drop_column("trip_items", "start_at")


def downgrade() -> None:
    op.add_column("trip_items", sa.Column("start_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("trip_items", sa.Column("end_at", sa.DateTime(timezone=True), nullable=True))
