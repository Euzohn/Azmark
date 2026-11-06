import uuid
from datetime import date

from sqlalchemy.orm import Session

from app.core.crypto import encrypt_value
from app.models.transport_record import TransportRecord
from app.repositories.transport import TransportRepository
from app.repositories.trip import TripRepository
from app.repositories.trip_item import TripItemRepository
from app.services.dedup import record_signature
from app.services.expense_source import SOURCE_TRANSPORT, clear_source, sync_source_trip
from app.services.seating import infer_train_seat_type
from app.services.write_lock import lock_user_writes


class RecordNotFoundError(Exception):
    pass


class TripAssignmentError(RecordNotFoundError):
    """The target trip does not exist or belongs to another user (spec #3.3/#57)."""


class DuplicateRecordError(Exception):
    """A record with the same deduplication key already exists (spec #41)."""

    def __init__(self, existing_record: TransportRecord) -> None:
        self.existing_record = existing_record
        super().__init__("Duplicate record")


# PNR、票号、购票证件号属敏感字段（spec #45/#96），一律加密存储。
_SENSITIVE_FIELDS = ("booking_reference", "ticket_number", "purchase_credential")


class TransportService:
    """Generic transport CRUD, scoped by user and record type (spec #11/#57)."""

    record_type: str = "flight"

    def __init__(self, db: Session) -> None:
        self.db = db
        self.records = TransportRepository(db)
        self.trips = TripRepository(db)
        self.trip_items = TripItemRepository(db)

    def _check_trip(self, *, user_id: uuid.UUID, trip_id: uuid.UUID | None) -> None:
        if trip_id is not None and self.trips.get(user_id=user_id, trip_id=trip_id) is None:
            raise TripAssignmentError

    def _check_duplicate(self, *, user_id: uuid.UUID, payload: dict) -> TransportRecord | None:
        """Check if a record with the same deduplication key already exists (spec #41)."""
        sig = record_signature(record_type=self.record_type, payload=payload)
        return self.records.find_by_signature(user_id=user_id, signature=sig)

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

    def _infer_seat_type(self, data: dict, *, seat_changed: bool = False) -> None:
        """Derive the seat position from the seat number (spec #13).

        Explicit values always win; on update we only infer when the seat itself
        changed, so clearing seat_type stays a deliberate choice.
        """
        if self.record_type != "train":
            return
        if data.get("seat_type"):
            return
        if seat_changed and "seat" not in data:
            return
        inferred = infer_train_seat_type(data.get("seat"))
        if inferred:
            data["seat_type"] = inferred

    def prepare_record(
        self,
        *,
        user_id: uuid.UUID,
        payload,
        force: bool = False,
        validate_refs: bool = True,
    ) -> TransportRecord:
        """Validate, normalize and encrypt an unsaved record.

        Shared with the v2 importer (docs §10.6) so the transport rules — trip
        ownership, dedup, seat inference and sensitive-field encryption — are
        never reimplemented by the import path. The importer resolves references
        from the bundle itself, so it passes ``validate_refs=False`` (rows are
        still pending and therefore invisible to a query).
        """
        data = payload.model_dump()
        if validate_refs:
            self._check_trip(user_id=user_id, trip_id=data.get("trip_id"))

        if not force:
            existing = self._check_duplicate(user_id=user_id, payload=data)
            if existing is not None:
                raise DuplicateRecordError(existing)

        self._infer_seat_type(data)
        enc = self._encrypt_sensitive(data)
        record = TransportRecord(user_id=user_id, type=self.record_type, **data)
        for field, cipher in enc.items():
            setattr(record, f"{field}_enc", cipher)
        return record

    def create_record(
        self,
        *,
        user_id: uuid.UUID,
        payload,
        force: bool = False,
        commit: bool = True,
    ) -> TransportRecord:
        lock_user_writes(self.db, user_id)
        record = self.prepare_record(user_id=user_id, payload=payload, force=force)
        record = self.records.create(record)
        self.trip_items.sync_transport(record)
        if commit:
            self.db.commit()
        return record

    def update_record(
        self, *, user_id: uuid.UUID, record_id: uuid.UUID, payload, commit: bool = True
    ) -> TransportRecord:
        lock_user_writes(self.db, user_id)
        record = self.get_record(user_id=user_id, record_id=record_id)
        was_unscheduled = record.departure_time is None
        previous_trip_id = record.trip_id
        data = payload.model_dump(exclude_unset=True)
        if "trip_id" in data:
            self._check_trip(user_id=user_id, trip_id=data["trip_id"])
        self._infer_seat_type(data, seat_changed=True)
        for field in _SENSITIVE_FIELDS:
            if field in data:
                value = data.pop(field)
                setattr(record, f"{field}_enc", encrypt_value(value) if value else None)
        for field, value in data.items():
            setattr(record, field, value)
        sync_source_trip(
            self.db,
            user_id=user_id,
            source_type=SOURCE_TRANSPORT,
            source_id=record.id,
            trip_id=record.trip_id,
        )
        record = self.records.save(record)
        self.trip_items.sync_transport(
            record,
            append_to_partition=(
                previous_trip_id == record.trip_id
                and was_unscheduled != (record.departure_time is None)
            ),
        )
        if commit:
            self.db.commit()
        return record

    def delete_record(
        self, *, user_id: uuid.UUID, record_id: uuid.UUID, commit: bool = True
    ) -> None:
        lock_user_writes(self.db, user_id)
        record = self.get_record(user_id=user_id, record_id=record_id)
        # Delete the source first so its row lock arbitrates a concurrent
        # expense bind. The later clear then always sees that expense.
        self.records.delete(record)
        clear_source(self.db, user_id=user_id, source_type=SOURCE_TRANSPORT, source_id=record.id)
        self.trip_items.delete_transport(user_id=user_id, record_id=record.id)
        if commit:
            self.db.commit()


class FlightService(TransportService):
    record_type = "flight"


class TrainService(TransportService):
    record_type = "train"


class OtherTransportService(TransportService):
    record_type = "other"
