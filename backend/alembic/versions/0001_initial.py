"""initial schema: users, transport_records

Revision ID: 0001
Revises:
Create Date: 2026-10-06

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=True),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("locale", sa.String(length=10), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index(op.f("ix_users_username"), "users", ["username"], unique=True)

    op.create_table(
        "transport_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("type", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("departure_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("arrival_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("departure_timezone", sa.String(length=64), nullable=True),
        sa.Column("arrival_timezone", sa.String(length=64), nullable=True),
        sa.Column("origin", sa.String(length=120), nullable=True),
        sa.Column("destination", sa.String(length=120), nullable=True),
        sa.Column("carrier", sa.String(length=120), nullable=True),
        sa.Column("service_number", sa.String(length=40), nullable=True),
        sa.Column("seat", sa.String(length=10), nullable=True),
        sa.Column("terminal", sa.String(length=20), nullable=True),
        sa.Column("gate", sa.String(length=20), nullable=True),
        sa.Column("booking_reference", sa.String(length=64), nullable=True),
        sa.Column("ticket_number", sa.String(length=64), nullable=True),
        sa.Column("price", sa.Numeric(12, 2), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("trip_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_transport_records_user_id"), "transport_records", ["user_id"])
    op.create_index(op.f("ix_transport_records_type"), "transport_records", ["type"])


def downgrade() -> None:
    op.drop_index(op.f("ix_transport_records_type"), table_name="transport_records")
    op.drop_index(op.f("ix_transport_records_user_id"), table_name="transport_records")
    op.drop_table("transport_records")
    op.drop_index(op.f("ix_users_username"), table_name="users")
    op.drop_table("users")
