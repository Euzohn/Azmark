"""add data sources

Revision ID: 0018
Revises: 0017
Create Date: 2026-10-20

Spec #22/#37 requires provenance for external data: source type, provider,
URL, retrieval time and confidence. All rows are user-scoped (spec #57).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "data_sources",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_type", sa.String(length=20), nullable=False),
        sa.Column("source_name", sa.String(length=255), nullable=False),
        sa.Column("source_url", sa.String(length=1000), nullable=True),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("provider", sa.String(length=40), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_data_sources_user_id"), "data_sources", ["user_id"], unique=False)
    op.create_index(
        op.f("ix_data_sources_source_type"), "data_sources", ["source_type"], unique=False
    )
    op.create_index(
        op.f("ix_data_sources_retrieved_at"), "data_sources", ["retrieved_at"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_data_sources_retrieved_at"), table_name="data_sources")
    op.drop_index(op.f("ix_data_sources_source_type"), table_name="data_sources")
    op.drop_index(op.f("ix_data_sources_user_id"), table_name="data_sources")
    op.drop_table("data_sources")
