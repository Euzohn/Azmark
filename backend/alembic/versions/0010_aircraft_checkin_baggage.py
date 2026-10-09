"""add aircraft, baggage, checkin fields

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-09

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "transport_records",
        sa.Column("check_in_desk", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "transport_records",
        sa.Column("baggage_belt", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "transport_records",
        sa.Column("aircraft_model", sa.String(length=60), nullable=True),
    )
    op.add_column(
        "transport_records",
        sa.Column("aircraft_reg", sa.String(length=20), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("transport_records", "aircraft_reg")
    op.drop_column("transport_records", "aircraft_model")
    op.drop_column("transport_records", "baggage_belt")
    op.drop_column("transport_records", "check_in_desk")
