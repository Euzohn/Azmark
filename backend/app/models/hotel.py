import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Float, ForeignKey, Numeric, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.crypto import decrypt_value
from app.core.db import Base
from app.models.user import utcnow


class Hotel(Base):
    """Hotel / accommodation stay (spec #17).

    Date-based, not datetime-based: a hotel night is identified by its check-in
    and check-out dates, so there are no timezone fields here. The booking
    reference is a confirmation number (spec #45/#96) and is encrypted at rest,
    mirroring how transport records treat PNRs.
    """

    __tablename__ = "hotels"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )

    hotel: Mapped[str] = mapped_column(String(160), nullable=False)
    check_in: Mapped[date] = mapped_column(Date, nullable=False)
    check_out: Mapped[date | None] = mapped_column(Date)

    room_type: Mapped[str | None] = mapped_column(String(60))
    room_number: Mapped[str | None] = mapped_column(String(20))

    # Confirmation number — sensitive (spec #45/#96); ciphertext only at rest.
    booking_reference_enc: Mapped[str | None] = mapped_column(Text)

    price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    currency: Mapped[str | None] = mapped_column(String(3))

    address: Mapped[str | None] = mapped_column(String(300))
    notes: Mapped[str | None] = mapped_column(Text)

    # Optional coordinates for the map (spec #10). Filled by the explicit
    # geocode action (Nominatim) or supplied by the caller; null until known.
    lat: Mapped[float | None] = mapped_column(Float)
    lon: Mapped[float | None] = mapped_column(Float)

    trip_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("trips.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Mirrors TransportRecord.status so the timeline/list can filter and badge.
    status: Mapped[str] = mapped_column(String(20), default="scheduled", nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="hotels")  # noqa: F821

    @property
    def booking_reference(self) -> str | None:
        """Decrypted confirmation number (spec #45/#96); ciphertext only at rest."""
        if not self.booking_reference_enc:
            return None
        return decrypt_value(self.booking_reference_enc)
