import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class TripItem(Base):
    """Ordered projection of a timeline event (spec #16).

    ``item_type`` is one of ``transport``/``hotel``/``activity``; the source
    entity owns membership and times, while this row keeps the stable item id
    and the display order. Legacy ``place`` items were converted to ``visit``
    Activities by migration 0027.
    """

    __tablename__ = "trip_items"
    __table_args__ = (
        CheckConstraint(
            "item_type IN ('transport', 'hotel', 'activity')",
            name="ck_trip_items_item_type",
        ),
        UniqueConstraint("trip_id", "item_type", "item_id", name="uq_trip_items_trip_item"),
        # One projection per source entity. Moving a record between trips keeps
        # the same row (and therefore the same stable item id).
        UniqueConstraint("user_id", "item_type", "item_id", name="uq_trip_items_user_entity"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    trip_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("trips.id", ondelete="CASCADE"), index=True, nullable=False
    )

    item_type: Mapped[str] = mapped_column(String(20), nullable=False, default="transport")
    item_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)

    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
