import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.crypto import decrypt_value
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

    # 实际起降时间（spec #12 actual_departure/actual_arrival）。
    actual_departure_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    actual_arrival_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    origin: Mapped[str | None] = mapped_column(String(120))
    destination: Mapped[str | None] = mapped_column(String(120))

    carrier: Mapped[str | None] = mapped_column(String(120))
    service_number: Mapped[str | None] = mapped_column(String(40))

    # Flight-specific
    seat: Mapped[str | None] = mapped_column(String(10))
    departure_terminal: Mapped[str | None] = mapped_column(String(20))
    departure_gate: Mapped[str | None] = mapped_column(String(20))
    arrival_terminal: Mapped[str | None] = mapped_column(String(20))
    arrival_gate: Mapped[str | None] = mapped_column(String(20))

    # PNR 预订编码与客票号属敏感字段（spec #45/#96），加密存储。
    booking_reference_enc: Mapped[str | None] = mapped_column(Text)
    ticket_number_enc: Mapped[str | None] = mapped_column(Text)

    # 购票证件号（身份证/护照）属敏感 PII（spec #45/#96），加密存储。
    purchase_credential_enc: Mapped[str | None] = mapped_column(Text)

    price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    currency: Mapped[str | None] = mapped_column(String(3))

    # 里程（km）。规格未列，按用户要求新增。
    distance: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))

    notes: Mapped[str | None] = mapped_column(Text)

    trip_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("trips.id", ondelete="SET NULL"), nullable=True, index=True
    )

    @property
    def booking_reference(self) -> str | None:
        """Decrypted PNR（spec #45/#96）；库中仅存密文。"""
        if not self.booking_reference_enc:
            return None
        return decrypt_value(self.booking_reference_enc)

    @property
    def ticket_number(self) -> str | None:
        """Decrypted ticket number（spec #45/#96）；库中仅存密文。"""
        if not self.ticket_number_enc:
            return None
        return decrypt_value(self.ticket_number_enc)

    @property
    def purchase_credential(self) -> str | None:
        """Decrypted purchase credential (spec #45/#96); ciphertext only at rest."""
        if not self.purchase_credential_enc:
            return None
        return decrypt_value(self.purchase_credential_enc)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="records")  # noqa: F821
