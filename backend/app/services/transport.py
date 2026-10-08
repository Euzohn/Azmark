import uuid

from sqlalchemy.orm import Session

from app.core.crypto import encrypt_value
from app.models.transport_record import TransportRecord
from app.repositories.transport import TransportRepository
from app.schemas.transport import FlightCreate, FlightUpdate


class RecordNotFoundError(Exception):
    pass


# PNR、票号、购票证件号属敏感字段（spec #45/#96），一律加密存储。
_SENSITIVE_FIELDS = ("booking_reference", "ticket_number", "purchase_credential")


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

    @staticmethod
    def _encrypt_sensitive(data: dict) -> dict[str, str | None]:
        """Pop sensitive plaintext fields and return {field: ciphertext} for non-empty values."""
        return {
            field: encrypt_value(value)
            for field in _SENSITIVE_FIELDS
            if (value := data.pop(field, None))
        }

    def create_flight(self, *, user_id: uuid.UUID, payload: FlightCreate) -> TransportRecord:
        data = payload.model_dump()
        enc = self._encrypt_sensitive(data)
        record = TransportRecord(user_id=user_id, type="flight", **data)
        for field, cipher in enc.items():
            setattr(record, f"{field}_enc", cipher)
        return self.records.create(record)

    def update_flight(
        self, *, user_id: uuid.UUID, record_id: uuid.UUID, payload: FlightUpdate
    ) -> TransportRecord:
        record = self.get_flight(user_id=user_id, record_id=record_id)
        data = payload.model_dump(exclude_unset=True)
        for field in _SENSITIVE_FIELDS:
            if field in data:
                value = data.pop(field)
                setattr(record, f"{field}_enc", encrypt_value(value) if value else None)
        for field, value in data.items():
            setattr(record, field, value)
        return self.records.save(record)

    def delete_flight(self, *, user_id: uuid.UUID, record_id: uuid.UUID) -> None:
        record = self.get_flight(user_id=user_id, record_id=record_id)
        self.records.delete(record)
