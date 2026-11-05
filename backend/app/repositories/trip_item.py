import uuid
from datetime import UTC, date, datetime, time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.hotel import Hotel
from app.models.transport_record import TransportRecord
from app.models.trip_item import TripItem

TRANSPORT_ITEM = "transport"
HOTEL_ITEM = "hotel"


def _as_utc(value: datetime | None) -> datetime | None:
    """Normalize a stored datetime for comparison (SQLite hands back naive values)."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _date_at_midnight(value: date | None) -> datetime | None:
    """Turn a hotel check-in/out date into a sortable UTC timestamp."""
    if value is None:
        return None
    return datetime.combine(value, time.min, tzinfo=UTC)


class TripItemRepository:
    """Trip membership/order rows (spec #16), always scoped by user_id."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def _chronological_sort_order(
        self, *, user_id: uuid.UUID, trip_id: uuid.UUID, start_at: datetime | None
    ) -> int:
        """Pick the sort_order where a new item with ``start_at`` belongs.

        The trip detail page reads as a timeline: a new item slots in before
        the first existing item that starts later, and items without a time
        sink to the end. Existing items at/after the slot shift down by one
        so sort_order stays contiguous. Manual reordering (set_order) still
        wins — this only decides where *new* items appear.
        """
        items = self.list_for_trip(user_id=user_id, trip_id=trip_id)
        target = _as_utc(start_at)
        position = len(items)
        for index, item in enumerate(items):
            existing = _as_utc(item.start_at)
            if target is not None and (existing is None or target < existing):
                position = index
                break
        for item in items[position:]:
            item.sort_order += 1
        return position

    def get_for_record(self, *, user_id: uuid.UUID, record_id: uuid.UUID) -> TripItem | None:
        return self.db.scalar(
            select(TripItem).where(
                TripItem.user_id == user_id,
                TripItem.item_type == TRANSPORT_ITEM,
                TripItem.item_id == record_id,
            )
        )

    def sync_transport(self, record: TransportRecord) -> None:
        """Mirror ``record.trip_id`` into TripItem, keeping times in sync."""
        item = self.get_for_record(user_id=record.user_id, record_id=record.id)

        if record.trip_id is None:
            if item is not None:
                self.db.delete(item)
                self.db.commit()
            return

        if item is None:
            item = TripItem(
                user_id=record.user_id,
                trip_id=record.trip_id,
                item_type=TRANSPORT_ITEM,
                item_id=record.id,
                sort_order=self._chronological_sort_order(
                    user_id=record.user_id, trip_id=record.trip_id, start_at=record.departure_time
                ),
                start_at=record.departure_time,
                end_at=record.arrival_time,
            )
            self.db.add(item)
        else:
            if item.trip_id != record.trip_id:
                # Moving between trips slots the record in at its time position.
                item.sort_order = self._chronological_sort_order(
                    user_id=record.user_id, trip_id=record.trip_id, start_at=record.departure_time
                )
                item.trip_id = record.trip_id
            item.start_at = record.departure_time
            item.end_at = record.arrival_time

        self.db.commit()

    def delete_transport(self, *, user_id: uuid.UUID, record_id: uuid.UUID) -> None:
        item = self.get_for_record(user_id=user_id, record_id=record_id)
        if item is not None:
            self.db.delete(item)
            self.db.commit()

    def get_for_hotel(self, *, user_id: uuid.UUID, hotel_id: uuid.UUID) -> TripItem | None:
        return self.db.scalar(
            select(TripItem).where(
                TripItem.user_id == user_id,
                TripItem.item_type == HOTEL_ITEM,
                TripItem.item_id == hotel_id,
            )
        )

    def sync_hotel(self, hotel: Hotel) -> None:
        """Mirror ``hotel.trip_id`` into TripItem, keeping dates in sync."""
        item = self.get_for_hotel(user_id=hotel.user_id, hotel_id=hotel.id)

        if hotel.trip_id is None:
            if item is not None:
                self.db.delete(item)
                self.db.commit()
            return

        if item is None:
            item = TripItem(
                user_id=hotel.user_id,
                trip_id=hotel.trip_id,
                item_type=HOTEL_ITEM,
                item_id=hotel.id,
                sort_order=self._chronological_sort_order(
                    user_id=hotel.user_id,
                    trip_id=hotel.trip_id,
                    start_at=_date_at_midnight(hotel.check_in),
                ),
                start_at=_date_at_midnight(hotel.check_in),
                end_at=_date_at_midnight(hotel.check_out),
            )
            self.db.add(item)
        else:
            if item.trip_id != hotel.trip_id:
                # Moving between trips slots the hotel in at its time position.
                item.sort_order = self._chronological_sort_order(
                    user_id=hotel.user_id,
                    trip_id=hotel.trip_id,
                    start_at=_date_at_midnight(hotel.check_in),
                )
                item.trip_id = hotel.trip_id
            item.start_at = _date_at_midnight(hotel.check_in)
            item.end_at = _date_at_midnight(hotel.check_out)

        self.db.commit()

    def delete_hotel(self, *, user_id: uuid.UUID, hotel_id: uuid.UUID) -> None:
        item = self.get_for_hotel(user_id=user_id, hotel_id=hotel_id)
        if item is not None:
            self.db.delete(item)
            self.db.commit()

    def list_for_trip(self, *, user_id: uuid.UUID, trip_id: uuid.UUID) -> list[TripItem]:
        stmt = (
            select(TripItem)
            .where(TripItem.user_id == user_id, TripItem.trip_id == trip_id)
            .order_by(TripItem.sort_order.asc(), TripItem.start_at.asc().nullslast(), TripItem.id)
        )
        return list(self.db.scalars(stmt))

    def get(self, *, user_id: uuid.UUID, trip_id: uuid.UUID, item_id: uuid.UUID) -> TripItem | None:
        return self.db.scalar(
            select(TripItem).where(
                TripItem.id == item_id,
                TripItem.user_id == user_id,
                TripItem.trip_id == trip_id,
            )
        )

    def save(self, item: TripItem) -> TripItem:
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def ensure_transport_items(self, *, user_id: uuid.UUID, trip_id: uuid.UUID) -> None:
        """Self-heal legacy/partial data: every grouped record gets an item.

        Missing records slot in at their chronological position so a mixed
        transport/hotel trip reads as a proper timeline.
        """
        records = list(
            self.db.scalars(
                select(TransportRecord).where(
                    TransportRecord.user_id == user_id,
                    TransportRecord.trip_id == trip_id,
                )
            )
        )
        record_ids = {record.id for record in records}
        items = self.list_for_trip(user_id=user_id, trip_id=trip_id)

        changed = False
        for item in items:
            if item.item_type == TRANSPORT_ITEM and item.item_id not in record_ids:
                self.db.delete(item)
                changed = True
        if changed:
            self.db.flush()

        survivors = self.list_for_trip(user_id=user_id, trip_id=trip_id)
        item_record_ids = {item.item_id for item in survivors if item.item_type == TRANSPORT_ITEM}
        _epoch = datetime.min.replace(tzinfo=UTC)
        missing = [record for record in records if record.id not in item_record_ids]
        missing.sort(
            key=lambda record: (
                _as_utc(record.departure_time) is None,
                _as_utc(record.departure_time) or _epoch,
                record.created_at,
            )
        )
        for record in missing:
            self.db.add(
                TripItem(
                    user_id=user_id,
                    trip_id=trip_id,
                    item_type=TRANSPORT_ITEM,
                    item_id=record.id,
                    sort_order=self._chronological_sort_order(
                        user_id=user_id, trip_id=trip_id, start_at=record.departure_time
                    ),
                    start_at=record.departure_time,
                    end_at=record.arrival_time,
                )
            )
            changed = True
            # Make the row visible to the next slot computation.
            self.db.flush()

        if changed:
            self.db.commit()

    def set_order(
        self, *, user_id: uuid.UUID, trip_id: uuid.UUID, item_ids: list[uuid.UUID]
    ) -> None:
        items = {item.id: item for item in self.list_for_trip(user_id=user_id, trip_id=trip_id)}
        for index, item_id in enumerate(item_ids):
            items[item_id].sort_order = index
        self.db.commit()
