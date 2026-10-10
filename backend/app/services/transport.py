import uuid
from datetime import date

from sqlalchemy.orm import Session

from app.core.crypto import encrypt_value
from app.models.transport_record import TransportRecord
from app.repositories.transport import TransportRepository


class RecordNotFoundError(Exception):
    pass


# PNR、票号、购票证件号属敏感字段（spec #45/#96），一律加密存储。
_SENSITIVE_FIELDS = ("booking_reference", "ticket_number", "purchase_credential")


class TransportService:
    """Generic transport CRUD, scoped by user and record type (spec #11/#57)."""

    record_type: str = "flight"

    def __init__(self, db: Session) -> None:
        self.records = TransportRepository(db)

    def list_records(
        self,
        *,
        user_id: uuid.UUID,
        search: str | None = None,
        status: str | None = None,
        cabin_class: str | None = None,
        trip_id: uuid.UUID | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[TransportRecord], int]:
        return self.records.list(
            user_id=user_id,
            record_type=self.record_type,
            search=search,
            status=status,
            cabin_class=cabin_class,
            trip_id=trip_id,
            date_from=date_from,
            date_to=date_to,
            page=page,
            page_size=page_size,
        )

    def get_record(self, *, user_id: uuid.UUID, record_id: uuid.UUID) -> TransportRecord:
        record = self.records.get(user_id=user_id, record_id=record_id)
        if record is None or record.type != self.record_type:
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

    def create_record(self, *, user_id: uuid.UUID, payload) -> TransportRecord:
        data = payload.model_dump()
        enc = self._encrypt_sensitive(data)
        record = TransportRecord(user_id=user_id, type=self.record_type, **data)
        for field, cipher in enc.items():
            setattr(record, f"{field}_enc", cipher)
        return self.records.create(record)

    def update_record(
        self, *, user_id: uuid.UUID, record_id: uuid.UUID, payload
    ) -> TransportRecord:
        record = self.get_record(user_id=user_id, record_id=record_id)
        data = payload.model_dump(exclude_unset=True)
        for field in _SENSITIVE_FIELDS:
            if field in data:
                value = data.pop(field)
                setattr(record, f"{field}_enc", encrypt_value(value) if value else None)
        for field, value in data.items():
            setattr(record, field, value)
        return self.records.save(record)

    def delete_record(self, *, user_id: uuid.UUID, record_id: uuid.UUID) -> None:
        record = self.get_record(user_id=user_id, record_id=record_id)
        self.records.delete(record)


class FlightService(TransportService):
    record_type = "flight"


class TrainService(TransportService):
    record_type = "train"
