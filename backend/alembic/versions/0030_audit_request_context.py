"""add audit request context (user_agent, request_id)

Revision ID: 0030
Revises: 0029
Create Date: 2026-11-09

Extends the audit trail (spec #47) with per-request correlation columns so an
operator can trace *which client / which request* produced a row, alongside the
existing salted ``ip_hash``. Both columns are nullable: historical rows keep
their existing shape, and background / non-HTTP audit entries (MCP tool calls
have no HTTP request body but do carry an ASGI request) simply leave them unset.

No sensitive raw values are introduced (spec #45, #96): ``user_agent`` is a
sanitised, truncated client hint and ``request_id`` is an opaque correlation id.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0030"
down_revision: str | None = "0029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "audit_logs",
        sa.Column("user_agent", sa.String(length=200), nullable=True),
    )
    op.add_column(
        "audit_logs",
        sa.Column("request_id", sa.String(length=64), nullable=True),
    )
    op.create_index(
        op.f("ix_audit_logs_request_id"),
        "audit_logs",
        ["request_id"],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_audit_logs_request_id"), table_name="audit_logs")
    op.drop_column("audit_logs", "request_id")
    op.drop_column("audit_logs", "user_agent")
