import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.place import Place
from app.models.user import utcnow


class Activity(Base):
    """Something done on a trip, optionally at a place (spec #18).

    A trip member like transport and hotels: ``trip_id`` is the canonical
    membership column and is mirrored into ``trip_items`` so the activity
    slots into the trip timeline at its ``start_at``.
    """

    __tablename__ = "activities"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # Small write vocabulary (spec #18 lists the field but no values);
    # the column stays a permissive String(40).
    type: Mapped[str] = mapped_column(String(40), default="other", nullable=False)

    place_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("places.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # Read-side summary for cards (docs §4.4). Joined so listing activities
    # does not issue one query per row.
    place: Mapped[Place | None] = relationship(lazy="joined")

    start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Display timezone of the event. Captured on creation (explicit value,
    # otherwise the place's timezone, otherwise the user's) so the timeline
    # keeps showing the local occurrence even if the referenced place changes.
    timezone: Mapped[str | None] = mapped_column(String(64))

    price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    currency: Mapped[str | None] = mapped_column(String(3))

    notes: Mapped[str | None] = mapped_column(Text)

    trip_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("trips.id", ondelete="SET NULL"), nullable=True, index=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
