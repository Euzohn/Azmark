import uuid
from datetime import date

from sqlalchemy.orm import Session

from app.models.transport_record import TransportRecord
from app.repositories.transport import TransportRepository


class RecordService:
    """Unified records list across transport types (spec #23)."""

    def __init__(self, db: Session) -> None:
        self.records = TransportRepository(db)

    def list_records(
        self,
        *,
        user_id: uuid.UUID,
        record_type: str | None = None,
        search: str | None = None,
        status: str | None = None,
        cabin_class: str | None = None,
        carrier: str | None = None,
        trip_id: uuid.UUID | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        sort: str = "newest",
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[TransportRecord], int]:
        return self.records.list(
            user_id=user_id,
            record_type=record_type,
            search=search,
            status=status,
            cabin_class=cabin_class,
            carrier=carrier,
            trip_id=trip_id,
            date_from=date_from,
            date_to=date_to,
            sort=sort,
            page=page,
            page_size=page_size,
        )
