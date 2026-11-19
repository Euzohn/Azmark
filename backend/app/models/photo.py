import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.user import utcnow


class Photo(Base):
    """A user-owned travel photo (spec #20, #44).

    Only metadata lives in PostgreSQL; the image and its thumbnail are stored
    through the StorageProvider under ``storage_key`` and
    ``storage_key + "/thumb"`` (never in the database).
    """

    __tablename__ = "photos"
    __table_args__ = (
        CheckConstraint(
            "latitude IS NULL OR (latitude >= -90 AND latitude <= 90)",
            name="ck_photos_latitude",
        ),
        CheckConstraint(
            "longitude IS NULL OR (longitude >= -180 AND longitude <= 180)",
            name="ck_photos_longitude",
        ),
        Index("ix_photos_owner_captured", "user_id", "captured_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )

    storage_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size: Mapped[int] = mapped_column(BigInteger, nullable=False)

    # EXIF-derived; nullable because exports and screenshots often carry none.
    captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)

    # A photo survives its trip (the trip is a filing cabinet, not an owner):
    # deleting the trip only unfiles the photo.
    trip_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("trips.id", ondelete="SET NULL"), nullable=True, index=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
