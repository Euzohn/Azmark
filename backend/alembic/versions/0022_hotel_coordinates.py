"""add hotel coordinates

Revision ID: 0022
Revises: 0021
Create Date: 2026-11-06

Spec #10/#17: the map shows hotels next to flight routes. Coordinates are
optional — a stay without them simply has no pin — and are filled on demand by
the geocode action (Nominatim) rather than guessed at creation time.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0022"
down_revision: str | None = "0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("hotels", sa.Column("lat", sa.Float(), nullable=True))
    op.add_column("hotels", sa.Column("lon", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("hotels", "lon")
    op.drop_column("hotels", "lat")
