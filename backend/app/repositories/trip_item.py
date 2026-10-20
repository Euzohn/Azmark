import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.transport_record import TransportRecord
from app.models.trip_item import TripItem

TRANSPORT_ITEM = "transport"


class TripItemRepository:
    """Trip membership/order rows (spec #16), always scoped by user_id."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def _next_sort_order(self, *, user_id: uuid.UUID, trip_id: uuid.UUID) -> int:
        current = self.db.scalar(
            select(func.max(TripItem.sort_order)).where(
                TripItem.user_id == user_id,
                TripItem.trip_id == trip_id,
            )
        )
        return int(current) + 1 if current is not None else 0

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
                sort_order=self._next_sort_order(user_id=record.user_id, trip_id=record.trip_id),
                start_at=record.departure_time,
                end_at=record.arrival_time,
            )
            self.db.add(item)
        else:
            if item.trip_id != record.trip_id:
                # Moving between trips appends to the destination trip.
                item.sort_order = self._next_sort_order(
                    user_id=record.user_id, trip_id=record.trip_id
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
        """Self-heal legacy/partial data: every grouped record gets an item."""
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
        item_record_ids = {item.item_id for item in items if item.item_type == TRANSPORT_ITEM}

        changed = False
        for item in items:
            if item.item_type == TRANSPORT_ITEM and item.item_id not in record_ids:
                self.db.delete(item)
                changed = True

        missing = [record for record in records if record.id not in item_record_ids]
        missing.sort(
            key=lambda record: (
                record.departure_time is None,
                record.departure_time,
                record.created_at,
            )
        )
        next_order = max((item.sort_order for item in items), default=-1) + 1
        for offset, record in enumerate(missing):
            self.db.add(
                TripItem(
                    user_id=user_id,
                    trip_id=trip_id,
                    item_type=TRANSPORT_ITEM,
                    item_id=record.id,
                    sort_order=next_order + offset,
                    start_at=record.departure_time,
                    end_at=record.arrival_time,
                )
            )
            changed = True

        if changed:
            self.db.commit()

    def set_order(
        self, *, user_id: uuid.UUID, trip_id: uuid.UUID, item_ids: list[uuid.UUID]
    ) -> None:
        items = {item.id: item for item in self.list_for_trip(user_id=user_id, trip_id=trip_id)}
        for index, item_id in enumerate(item_ids):
            items[item_id].sort_order = index
        self.db.commit()
