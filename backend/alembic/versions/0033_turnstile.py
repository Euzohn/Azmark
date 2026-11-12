"""add Turnstile captcha provider columns to system_settings

Revision ID: 0033
Revises: 0032
Create Date: 2026-11-12

Bot protection gains a second provider: Cloudflare Turnstile (spec #60).
``captcha_provider`` selects "arithmetic" (self-hosted default) or "turnstile";
the Turnstile secret is Fernet-encrypted and never returned by the API. While
Turnstile is not fully configured (site key or secret missing) the register
flow transparently falls back to the arithmetic challenge, so the door is
never left open by a half-configured provider.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0033"
down_revision: str | None = "0032"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "system_settings",
        sa.Column(
            "captcha_provider",
            sa.String(length=20),
            nullable=False,
            server_default="arithmetic",
        ),
    )
    op.add_column(
        "system_settings",
        sa.Column("turnstile_site_key", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "system_settings",
        sa.Column("turnstile_secret_key_enc", sa.String(length=512), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("system_settings", "turnstile_secret_key_enc")
    op.drop_column("system_settings", "turnstile_site_key")
    op.drop_column("system_settings", "captcha_provider")
