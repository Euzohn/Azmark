"""add storage quota

Revision ID: 0035
Revises: 0034
Create Date: 2026-11-20

Admins cap how much object storage a user may occupy. ``users.storage_quota_bytes``
is a per-user override (NULL = follow the instance default, 0 = unlimited); the
instance default lives in ``system_settings`` and starts at 0, so existing users
are not retroactively blocked. Usage is the sum of attachment and photo sizes,
computed from the rows themselves — deleting a file frees quota immediately.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0035"
down_revision: str | None = "0034"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("storage_quota_bytes", sa.BigInteger(), nullable=True))
    op.add_column(
        "system_settings",
        sa.Column(
            "default_storage_quota_bytes",
            sa.BigInteger(),
            server_default="0",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("system_settings", "default_storage_quota_bytes")
    op.drop_column("users", "storage_quota_bytes")
