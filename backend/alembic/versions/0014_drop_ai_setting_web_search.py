"""drop the unused user_ai_settings.web_search flag

Revision ID: 0014
Revises: 0013
Create Date: 2026-10-20

Web search is done through the SearchProvider abstraction (spec #37, #66), so
this flag was never wired to anything: no UI toggle rendered it and the AI
agent never read it. Dropping it removes a misleading affordance.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("user_ai_settings", "web_search")


def downgrade() -> None:
    op.add_column(
        "user_ai_settings", sa.Column("web_search", sa.Boolean(), nullable=False)
    )
