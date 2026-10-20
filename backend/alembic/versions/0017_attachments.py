"""add file attachments

Revision ID: 0017
Revises: 0016
Create Date: 2026-10-20

Spec #44 keeps binaries in S3-compatible object storage and only stores the
opaque ``storage_key`` plus metadata in PostgreSQL.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "attachments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("resource_type", sa.String(length=20), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=False),
        sa.Column("storage_key", sa.String(length=255), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=False),
        sa.Column("size", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key", name="uq_attachments_storage_key"),
    )
    op.create_index(op.f("ix_attachments_user_id"), "attachments", ["user_id"], unique=False)
    op.create_index(
        op.f("ix_attachments_created_at"), "attachments", ["created_at"], unique=False
    )
    op.create_index(
        "ix_attachments_owner_resource",
        "attachments",
        ["user_id", "resource_type", "resource_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_attachments_owner_resource", table_name="attachments")
    op.drop_index(op.f("ix_attachments_created_at"), table_name="attachments")
    op.drop_index(op.f("ix_attachments_user_id"), table_name="attachments")
    op.drop_table("attachments")
