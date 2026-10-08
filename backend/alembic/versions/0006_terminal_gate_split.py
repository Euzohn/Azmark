"""split terminal/gate into departure and arrival

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-09

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "transport_records",
        sa.Column("departure_terminal", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "transport_records",
        sa.Column("departure_gate", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "transport_records",
        sa.Column("arrival_terminal", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "transport_records",
        sa.Column("arrival_gate", sa.String(length=20), nullable=True),
    )
    # 旧 terminal/gate 按出发端迁移。
    connection = op.get_bind()
    connection.execute(
        sa.text(
            "UPDATE transport_records SET departure_terminal = terminal WHERE terminal IS NOT NULL"
        )
    )
    connection.execute(
        sa.text("UPDATE transport_records SET departure_gate = gate WHERE gate IS NOT NULL")
    )
    op.drop_column("transport_records", "terminal")
    op.drop_column("transport_records", "gate")


def downgrade() -> None:
    op.add_column(
        "transport_records",
        sa.Column("terminal", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "transport_records",
        sa.Column("gate", sa.String(length=20), nullable=True),
    )
    connection = op.get_bind()
    connection.execute(
        sa.text(
            "UPDATE transport_records SET terminal = departure_terminal"
            " WHERE departure_terminal IS NOT NULL"
        )
    )
    connection.execute(
        sa.text(
            "UPDATE transport_records SET gate = departure_gate WHERE departure_gate IS NOT NULL"
        )
    )
    op.drop_column("transport_records", "arrival_gate")
    op.drop_column("transport_records", "arrival_terminal")
    op.drop_column("transport_records", "departure_gate")
    op.drop_column("transport_records", "departure_terminal")
