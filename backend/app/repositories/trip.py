import uuid

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models.transport_record import TransportRecord
from app.models.trip import Trip


class TripRepository:
    """All queries are scoped by user_id — callers must never bypass it (spec #57)."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def list_trips(
        self,
        *,
        user_id: uuid.UUID,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Trip], int]:
        total = self.db.scalar(
            select(func.count()).select_from(Trip).where(Trip.user_id == user_id)
        )
        stmt = (
            select(Trip)
            .where(Trip.user_id == user_id)
            .order_by(
                Trip.start_date.desc().nullslast(),
                Trip.created_at.desc(),
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(self.db.scalars(stmt)), int(total or 0)

    def get(self, *, user_id: uuid.UUID, trip_id: uuid.UUID) -> Trip | None:
        return self.db.scalar(select(Trip).where(Trip.id == trip_id, Trip.user_id == user_id))

    def create(self, trip: Trip) -> Trip:
        self.db.add(trip)
        self.db.commit()
        self.db.refresh(trip)
        return trip

    def save(self, trip: Trip) -> Trip:
        self.db.add(trip)
        self.db.commit()
        self.db.refresh(trip)
        return trip

    def delete(self, trip: Trip) -> None:
        self.db.delete(trip)
        self.db.commit()

    def clear_records(self, *, user_id: uuid.UUID, trip_id: uuid.UUID) -> None:
        """Unlink the trip's records so they are not orphaned (spec #57)."""
        self.db.execute(
            update(TransportRecord)
            .where(
                TransportRecord.user_id == user_id,
                TransportRecord.trip_id == trip_id,
            )
            .values(trip_id=None)
        )
        self.db.commit()

    def list_flights(self, *, user_id: uuid.UUID, trip_id: uuid.UUID) -> list[TransportRecord]:
        stmt = (
            select(TransportRecord)
            .where(
                TransportRecord.user_id == user_id,
                TransportRecord.trip_id == trip_id,
                TransportRecord.type == "flight",
            )
            .order_by(
                TransportRecord.departure_time.asc().nullslast(),
                TransportRecord.created_at.asc(),
            )
        )
        return list(self.db.scalars(stmt))
