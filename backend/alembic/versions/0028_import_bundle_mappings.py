"""idempotent v2 import bundle mappings

Revision ID: 0028
Revises: 0027
Create Date: 2026-11-06

Persists the relation between an exported entity id and the target row created
for a given user's import bundle (docs/data-model.md §10.6). Re-importing the
same bundle reuses these rows instead of duplicating data; the table never
holds ownership or content, only the mapping.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0028"
down_revision: str | None = "0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "import_bundle_mappings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("bundle_id", sa.String(length=64), nullable=False),
        sa.Column("entity_type", sa.String(length=20), nullable=False),
        sa.Column("exported_id", sa.String(length=64), nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "bundle_id",
            "entity_type",
            "exported_id",
            name="uq_import_mappings_user_bundle_entity",
        ),
    )
    op.create_index(
        "ix_import_mappings_user_bundle",
        "import_bundle_mappings",
        ["user_id", "bundle_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_import_mappings_user_bundle", table_name="import_bundle_mappings")
    op.drop_table("import_bundle_mappings")
