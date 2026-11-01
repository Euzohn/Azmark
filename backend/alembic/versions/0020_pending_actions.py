"""add pending actions

Revision ID: 0020
Revises: 0019
Create Date: 2026-11-01

Spec #69/#85: an agent must not be able to approve its own write. MCP write
tool calls are stored here and executed only after a human confirms them in the
web UI, so the row carries both the owner and the token that asked.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0020"
down_revision: str | None = "0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "pending_actions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "token_id",
            sa.Uuid(),
            sa.ForeignKey("personal_access_tokens.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("token_name", sa.String(length=100), nullable=True),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column("record_type", sa.String(length=20), nullable=False),
        sa.Column("summary", sa.String(length=500), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("error", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_pending_actions_user_id"), "pending_actions", ["user_id"], unique=False
    )
    op.create_index(
        op.f("ix_pending_actions_token_id"), "pending_actions", ["token_id"], unique=False
    )
    op.create_index(op.f("ix_pending_actions_status"), "pending_actions", ["status"], unique=False)
    op.create_index(
        op.f("ix_pending_actions_created_at"), "pending_actions", ["created_at"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_pending_actions_created_at"), table_name="pending_actions")
    op.drop_index(op.f("ix_pending_actions_status"), table_name="pending_actions")
    op.drop_index(op.f("ix_pending_actions_token_id"), table_name="pending_actions")
    op.drop_index(op.f("ix_pending_actions_user_id"), table_name="pending_actions")
    op.drop_table("pending_actions")
