"""instance-level system settings (registration policy, captcha, SMTP)

Revision ID: 0032
Revises: 0031
Create Date: 2026-11-12

Single-row table (id=1) editable by admins at runtime. Secure defaults:
self-registration disabled and registration captcha off — an existing
deployment upgrading to this revision has its door closed until an admin
opens it. The SMTP password is stored Fernet-encrypted (key derived from
SECRET_KEY); it is never returned by the API.
"""

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op

revision: str = "0032"
down_revision: str | None = "0031"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    system_settings = op.create_table(
        "system_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("allow_registration", sa.Boolean(), nullable=False),
        sa.Column("registration_captcha_enabled", sa.Boolean(), nullable=False),
        sa.Column("smtp_host", sa.String(length=255), nullable=True),
        sa.Column("smtp_port", sa.Integer(), nullable=True),
        sa.Column("smtp_username", sa.String(length=255), nullable=True),
        sa.Column("smtp_password_enc", sa.String(length=512), nullable=True),
        sa.Column("smtp_sender", sa.String(length=255), nullable=True),
        sa.Column("smtp_starttls", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.bulk_insert(
        system_settings,
        [
            {
                "id": 1,
                "allow_registration": False,
                "registration_captcha_enabled": False,
                "smtp_starttls": True,
                "updated_at": datetime.now(UTC),
            }
        ],
    )


def downgrade() -> None:
    op.drop_table("system_settings")
