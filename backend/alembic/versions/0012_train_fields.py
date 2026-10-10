"""add train-specific fields

Revision ID: 0012
Revises: 0011
Create Date: 2026-10-10

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "transport_records",
        sa.Column("train_type", sa.String(length=30), nullable=True),
    )
    op.add_column(
        "transport_records",
        sa.Column("carriage", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "transport_records",
        sa.Column("seat_type", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "transport_records",
        sa.Column("ticket_type", sa.String(length=30), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("transport_records", "ticket_type")
    op.drop_column("transport_records", "seat_type")
    op.drop_column("transport_records", "carriage")
    op.drop_column("transport_records", "train_type")
