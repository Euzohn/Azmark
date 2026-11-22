"""password age reminder

Revision ID: 0036
Revises: 0035
Create Date: 2026-11-21

Admins can ask users to rotate their password after a configurable number of
days (``system_settings.password_max_age_days``, 0 = disabled — opt-in, no
retroactive nagging). The age is measured from ``users.password_changed_at``.

Existing rows never recorded a password change, so the column is backfilled
with ``created_at``: the account's creation is the oldest the password can
possibly be, which reminds conservatively (earlier rather than later). New
registrations and every password write (self-service change, admin bootstrap
reset) stamp the column from now on.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0036"
down_revision: str | None = "0035"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users", sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.execute(
        "UPDATE users SET password_changed_at = created_at WHERE password_changed_at IS NULL"
    )
    op.add_column(
        "system_settings",
        sa.Column("password_max_age_days", sa.Integer(), server_default="0", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("system_settings", "password_max_age_days")
    op.drop_column("users", "password_changed_at")
