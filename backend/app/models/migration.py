import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.user import utcnow


class TimelineMigrationArchive(Base):
    """Immutable audit row describing how a legacy timeline item was migrated.

    Archives are user-scoped migration evidence, not business data: they are
    never read by the timeline or statistics. ``original_item_id`` plus
    ``migration_key`` makes reruns idempotent, and ``item_id`` is kept as a
    historical identifier even after the target record is deleted.
    """

    __tablename__ = "timeline_migration_archives"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "migration_key",
            "original_item_id",
            name="uq_timeline_archives_user_key_item",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )

    migration_key: Mapped[str] = mapped_column(String(64), nullable=False)
    original_item_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    trip_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    item_type: Mapped[str] = mapped_column(String(20), nullable=False)
    item_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)

    # Original projection values before the migration touched the row.
    start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # What the source record contained at migration time, when applicable.
    source_start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    diff_type: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    user_choice: Mapped[str | None] = mapped_column(String(40))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class PlaceVisitMapping(Base):
    """Legacy place trip item → visit Activity, kept across reruns."""

    __tablename__ = "place_visit_mappings"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "migration_key",
            "original_item_id",
            name="uq_place_visit_mappings_user_key_item",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    migration_key: Mapped[str] = mapped_column(String(64), nullable=False)
    original_item_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    # Historical identifier: intentionally no foreign key, so deleting the
    # Activity later never erases the migration trail.
    activity_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
