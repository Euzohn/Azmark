import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class TripItem(Base):
    """Ordered member of a Trip (spec #16).

    ``item_type``/``item_id`` are polymorphic so hotels, places and activities
    can join later. Today only ``transport`` items exist and mirror
    ``TransportRecord.trip_id`` (the canonical membership column).
    """

    __tablename__ = "trip_items"
    __table_args__ = (
        UniqueConstraint("trip_id", "item_type", "item_id", name="uq_trip_items_trip_item"),
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
