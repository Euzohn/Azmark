from __future__ import annotations

import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.transport_record import TransportRecord


class TransportRepository:
    """All queries are scoped by user_id — callers must never bypass it (spec #57)."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def list(
        self,
        *,
        user_id: uuid.UUID,
        record_type: str = "flight",
        search: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[TransportRecord], int]:
        filters = [TransportRecord.user_id == user_id, TransportRecord.type == record_type]
        if search:
            like = f"%{search}%"
            filters.append(
                or_(
                    TransportRecord.origin.ilike(like),
                    TransportRecord.destination.ilike(like),
                    TransportRecord.service_number.ilike(like),
                    TransportRecord.carrier.ilike(like),
                )
            )

        total = self.db.scalar(select(func.count()).select_from(TransportRecord).where(*filters))
        stmt = (
            select(TransportRecord)
            .where(*filters)
            .order_by(
                TransportRecord.departure_time.desc().nullslast(),
                TransportRecord.created_at.desc(),
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(self.db.scalars(stmt)), int(total or 0)

    def get(self, *, user_id: uuid.UUID, record_id: uuid.UUID) -> TransportRecord | None:
        return self.db.scalar(
            select(TransportRecord).where(
                TransportRecord.id == record_id,
                TransportRecord.user_id == user_id,
            )
        )

    def list_all(
        self,
        *,
        user_id: uuid.UUID,
        limit: int = 5000,
    ) -> list[TransportRecord]:
        """Return all records for a user ordered by departure time desc."""
        stmt = (
            select(TransportRecord)
            .where(TransportRecord.user_id == user_id)
            .order_by(
                TransportRecord.departure_time.desc().nullslast(),
                TransportRecord.created_at.desc(),
            )
            .limit(limit)
        )
        return list(self.db.scalars(stmt))

    def create(self, record: TransportRecord) -> TransportRecord:
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def save(self, record: TransportRecord) -> TransportRecord:
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def delete(self, record: TransportRecord) -> None:
        self.db.delete(record)
        self.db.commit()
