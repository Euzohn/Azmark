import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.user import utcnow


class Expense(Base):
    """A spending record (spec #19). P1 feature, optionally linked to a trip.

    The amount is always stored together with its own currency; conversion to a
    reporting currency is a separate, optional pair of columns so a record is
    never reduced to a single (lossy) number.
    """

    __tablename__ = "expenses"
    __table_args__ = (
        CheckConstraint(
            "(source_type IS NULL AND source_id IS NULL) "
            "OR (source_type IS NOT NULL AND source_id IS NOT NULL)",
            name="ck_expenses_source_pair",
        ),
        CheckConstraint(
            "source_type IS NULL OR source_type IN ('transport', 'hotel', 'activity')",
            name="ck_expenses_source_type",
        ),
        Index("ix_expenses_source", "user_id", "source_type", "source_id"),
        Index("ix_expenses_user_trip", "user_id", "trip_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )

    category: Mapped[str] = mapped_column(String(40), default="other", nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)

    converted_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    converted_currency: Mapped[str | None] = mapped_column(String(3))
    exchange_rate: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))
    exchange_rate_date: Mapped[date | None] = mapped_column(Date)

    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    description: Mapped[str | None] = mapped_column(Text)

    trip_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("trips.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Optional link to the record this spend paid for. Type is the entity
    # vocabulary (transport/hotel/activity); a transport record's own ``type``
    # tells flight/train/other. The pair is atomic (database check).
    source_type: Mapped[str | None] = mapped_column(String(20))
    source_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
