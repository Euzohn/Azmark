import uuid

from sqlalchemy.orm import Session

from app.models.transport_record import TransportRecord
from app.repositories.transport import TransportRepository
from app.schemas.transport import FlightCreate, FlightUpdate


class RecordNotFoundError(Exception):
    pass


class FlightService:
    def __init__(self, db: Session) -> None:
        self.records = TransportRepository(db)

    def list_flights(
        self,
        *,
        user_id: uuid.UUID,
        search: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[TransportRecord], int]:
        return self.records.list(
            user_id=user_id,
            record_type="flight",
            search=search,
            page=page,
            page_size=page_size,
        )

    def get_flight(self, *, user_id: uuid.UUID, record_id: uuid.UUID) -> TransportRecord:
        record = self.records.get(user_id=user_id, record_id=record_id)
        if record is None:
            raise RecordNotFoundError
        return record

    def create_flight(self, *, user_id: uuid.UUID, payload: FlightCreate) -> TransportRecord:
        record = TransportRecord(user_id=user_id, type="flight", **payload.model_dump())
        return self.records.create(record)

    def update_flight(
        self, *, user_id: uuid.UUID, record_id: uuid.UUID, payload: FlightUpdate
    ) -> TransportRecord:
        record = self.get_flight(user_id=user_id, record_id=record_id)
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(record, field, value)
        return self.records.save(record)

    def delete_flight(self, *, user_id: uuid.UUID, record_id: uuid.UUID) -> None:
        record = self.get_flight(user_id=user_id, record_id=record_id)
        self.records.delete(record)
