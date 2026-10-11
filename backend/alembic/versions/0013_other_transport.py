"""add other-transport vehicle type

Revision ID: 0013
Revises: 0012
Create Date: 2026-10-12

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "transport_records",
        sa.Column("vehicle_type", sa.String(length=30), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("transport_records", "vehicle_type")
