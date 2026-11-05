import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.user import utcnow


class Place(Base):
    """A geographic point the user visited or will visit (spec #14).

    A geo reference, not a trip member: it carries no ``trip_id``. It joins a
    trip only through an explicit ``trip_items`` row (``item_type='place'``)
    whose ``start_at``/``end_at`` hold the visit window, and activities may
    reference it via ``place_id``. ``external_ids`` keeps loose links to
    outside registries (e.g. ``{"osm": "..."}``).
    """

    __tablename__ = "places"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )

    # Vocabulary in spec #14: airport, train_station, bus_station, port, hotel,
    # restaurant, attraction, city, place, other. The column stays permissive.
    type: Mapped[str] = mapped_column(String(20), default="place", nullable=False)

    country: Mapped[str | None] = mapped_column(String(120))
    region: Mapped[str | None] = mapped_column(String(120))
    city: Mapped[str | None] = mapped_column(String(120))
    district: Mapped[str | None] = mapped_column(String(120))

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    localized_name: Mapped[str | None] = mapped_column(String(200))

    lat: Mapped[float | None] = mapped_column(Float)
    lon: Mapped[float | None] = mapped_column(Float)
    timezone: Mapped[str | None] = mapped_column(String(64))

    external_ids: Mapped[dict | None] = mapped_column(JSON)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
