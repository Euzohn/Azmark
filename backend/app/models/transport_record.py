import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.user import utcnow


class TransportRecord(Base):
    """Unified transport model (see spec #11). Flight-specific fields are nullable."""

    __tablename__ = "transport_records"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    type: Mapped[str] = mapped_column(String(20), default="flight", nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), default="scheduled", nullable=False)

    departure_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    arrival_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    departure_timezone: Mapped[str | None] = mapped_column(String(64))
    arrival_timezone: Mapped[str | None] = mapped_column(String(64))

    origin: Mapped[str | None] = mapped_column(String(120))
    destination: Mapped[str | None] = mapped_column(String(120))

    carrier: Mapped[str | None] = mapped_column(String(120))
    service_number: Mapped[str | None] = mapped_column(String(40))

    # Flight-specific
    seat: Mapped[str | None] = mapped_column(String(10))
    terminal: Mapped[str | None] = mapped_column(String(20))
    gate: Mapped[str | None] = mapped_column(String(20))

    booking_reference: Mapped[str | None] = mapped_column(String(64))
    ticket_number: Mapped[str | None] = mapped_column(String(64))

    price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    currency: Mapped[str | None] = mapped_column(String(3))

    notes: Mapped[str | None] = mapped_column(Text)

    trip_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="records")  # noqa: F821
