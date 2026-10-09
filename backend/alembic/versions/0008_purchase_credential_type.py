"""add purchase_credential_type

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-09

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "transport_records",
        sa.Column("purchase_credential_type", sa.String(length=20), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("transport_records", "purchase_credential_type")
