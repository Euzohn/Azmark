"""add airline_code

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-09

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "transport_records",
        sa.Column("airline_code", sa.String(length=3), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("transport_records", "airline_code")
