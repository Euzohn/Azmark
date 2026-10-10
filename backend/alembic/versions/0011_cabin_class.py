"""add cabin class field

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-10

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "transport_records",
        sa.Column("cabin_class", sa.String(length=20), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("transport_records", "cabin_class")
