"""add photos

Revision ID: 0034
Revises: 0033
Create Date: 2026-11-20

Photo becomes a first-class record (spec #20, #82): the binary lives in
S3-compatible storage through the StorageProvider (spec #44) and PostgreSQL
keeps only ``storage_key`` plus metadata. EXIF-derived ``captured_at`` and
coordinates let photos join the timeline, the map and the AI journal later;
``trip_id`` is a filing cabinet, not an owner, so deleting a trip only unfiles
its photos.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0034"
down_revision: str | None = "0033"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "photos",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("storage_key", sa.String(length=255), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=False),
        sa.Column("size", sa.BigInteger(), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column(
            "trip_id",
            sa.Uuid(),
            sa.ForeignKey("trips.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key", name="uq_photos_storage_key"),
        sa.CheckConstraint(
            "latitude IS NULL OR (latitude >= -90 AND latitude <= 90)",
            name="ck_photos_latitude",
        ),
        sa.CheckConstraint(
            "longitude IS NULL OR (longitude >= -180 AND longitude <= 180)",
            name="ck_photos_longitude",
        ),
    )
    op.create_index(op.f("ix_photos_user_id"), "photos", ["user_id"], unique=False)
    op.create_index(op.f("ix_photos_trip_id"), "photos", ["trip_id"], unique=False)
    op.create_index("ix_photos_owner_captured", "photos", ["user_id", "captured_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_photos_owner_captured", table_name="photos")
    op.drop_index(op.f("ix_photos_trip_id"), table_name="photos")
    op.drop_index(op.f("ix_photos_user_id"), table_name="photos")
    op.drop_table("photos")
