import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.activity import Activity
from app.models.hotel import Hotel
from app.models.transport_record import TransportRecord
from app.models.trip import Trip
from app.models.trip_item import TripItem

TRANSPORT_ITEM = "transport"
HOTEL_ITEM = "hotel"
ACTIVITY_ITEM = "activity"

TIMELINE_ITEM_TYPES = (TRANSPORT_ITEM, HOTEL_ITEM, ACTIVITY_ITEM)


class TripItemRepository:
    """Trip membership/order rows (spec #16), always scoped by user_id.

    ``trip_items`` is a projection: membership comes from the source record's
    ``trip_id`` and event times come from the source entity. The row only adds
    a stable item id and the display order. ``start_at/end_at`` are legacy
    columns kept until the final cleanup migration.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def _next_sort_order(self, *, user_id: uuid.UUID, trip_id: uuid.UUID) -> int:
        """Append to the trip; chronological display order is derived on read."""
        current = self.db.scalar(
            select(func.max(TripItem.sort_order)).where(
                TripItem.user_id == user_id, TripItem.trip_id == trip_id
            )
        )
        return int(current) + 1 if current is not None else 0

    def _sync_entity(
        self, *, item_type: str, entity_id: uuid.UUID, user_id: uuid.UUID, trip_id: uuid.UUID | None
    ) -> None:
        item = self.db.scalar(
            select(TripItem).where(
                TripItem.user_id == user_id,
                TripItem.item_type == item_type,
                TripItem.item_id == entity_id,
            )
        )

        if trip_id is None:
            if item is not None:
                self.db.delete(item)
            self.db.flush()
            return

        if item is None:
            self.db.add(
                TripItem(
                    user_id=user_id,
                    trip_id=trip_id,
                    item_type=item_type,
                    item_id=entity_id,
                    sort_order=self._next_sort_order(user_id=user_id, trip_id=trip_id),
                )
            )
        else:
            if item.trip_id != trip_id:
                # Moving between trips keeps the stable item id and appends to
                # the target's order; chronological display recomputes anyway.
                item.sort_order = self._next_sort_order(user_id=user_id, trip_id=trip_id)
                item.trip_id = trip_id
        self.db.flush()

    def get_for_record(self, *, user_id: uuid.UUID, record_id: uuid.UUID) -> TripItem | None:
        return self._get_entity(user_id=user_id, item_type=TRANSPORT_ITEM, entity_id=record_id)

    def sync_transport(self, record: TransportRecord) -> None:
        self._sync_entity(
            item_type=TRANSPORT_ITEM,
            entity_id=record.id,
            user_id=record.user_id,
            trip_id=record.trip_id,
        )

    def delete_transport(self, *, user_id: uuid.UUID, record_id: uuid.UUID) -> None:
        item = self.get_for_record(user_id=user_id, record_id=record_id)
        if item is not None:
            self.db.delete(item)
            self.db.flush()

    def get_for_hotel(self, *, user_id: uuid.UUID, hotel_id: uuid.UUID) -> TripItem | None:
        return self._get_entity(user_id=user_id, item_type=HOTEL_ITEM, entity_id=hotel_id)

    def sync_hotel(self, hotel: Hotel) -> None:
        self._sync_entity(
            item_type=HOTEL_ITEM,
            entity_id=hotel.id,
            user_id=hotel.user_id,
            trip_id=hotel.trip_id,
        )

    def delete_hotel(self, *, user_id: uuid.UUID, hotel_id: uuid.UUID) -> None:
        item = self.get_for_hotel(user_id=user_id, hotel_id=hotel_id)
        if item is not None:
            self.db.delete(item)
            self.db.flush()

    def get_for_activity(self, *, user_id: uuid.UUID, activity_id: uuid.UUID) -> TripItem | None:
        return self._get_entity(user_id=user_id, item_type=ACTIVITY_ITEM, entity_id=activity_id)

    def sync_activity(self, activity: Activity) -> None:
        self._sync_entity(
            item_type=ACTIVITY_ITEM,
            entity_id=activity.id,
            user_id=activity.user_id,
            trip_id=activity.trip_id,
        )

    def delete_activity(self, *, user_id: uuid.UUID, activity_id: uuid.UUID) -> None:
        item = self.get_for_activity(user_id=user_id, activity_id=activity_id)
        if item is not None:
            self.db.delete(item)
            self.db.flush()

    def _get_entity(
        self, *, user_id: uuid.UUID, item_type: str, entity_id: uuid.UUID
    ) -> TripItem | None:
        return self.db.scalar(
            select(TripItem).where(
                TripItem.user_id == user_id,
                TripItem.item_type == item_type,
                TripItem.item_id == entity_id,
            )
        )

    def delete_item(self, item: TripItem) -> None:
        self.db.delete(item)
        self.db.flush()

    def list_for_trip(self, *, user_id: uuid.UUID, trip_id: uuid.UUID) -> list[TripItem]:
        stmt = (
            select(TripItem)
            .where(TripItem.user_id == user_id, TripItem.trip_id == trip_id)
            .order_by(TripItem.sort_order.asc(), TripItem.id)
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
        self.db.flush()
        self.db.refresh(item)
        return item

    def repair_timeline(self, *, user_id: uuid.UUID, trip_id: uuid.UUID) -> dict[str, int]:
        """Bring projections in line with source records, without reading.

        - deletes projections whose source is gone or no longer belongs here;
        - reassigns a projection that still sits in the old trip;
        - adds projections missing for sources that belong to this trip.

        Legacy place items were converted by migration 0027.
        Idempotent and user-scoped.
        """
        sources: dict[str, dict[uuid.UUID, object]] = {
            TRANSPORT_ITEM: {
                record.id: record
                for record in self.db.scalars(
                    select(TransportRecord).where(
                        TransportRecord.user_id == user_id,
                        TransportRecord.trip_id == trip_id,
                    )
                )
            },
            HOTEL_ITEM: {
                hotel.id: hotel
                for hotel in self.db.scalars(
                    select(Hotel).where(Hotel.user_id == user_id, Hotel.trip_id == trip_id)
                )
            },
            ACTIVITY_ITEM: {
                activity.id: activity
                for activity in self.db.scalars(
                    select(Activity).where(Activity.user_id == user_id, Activity.trip_id == trip_id)
                )
            },
        }

        added = fixed = removed = 0
        for item_type, entities in sources.items():
            entity_ids = list(entities)
            projections = list(
                self.db.scalars(
                    select(TripItem).where(
                        TripItem.user_id == user_id,
                        TripItem.item_type == item_type,
                        or_(
                            TripItem.trip_id == trip_id,
                            TripItem.item_id.in_(entity_ids),
                        )
                        if entity_ids
                        else TripItem.trip_id == trip_id,
                    )
                )
            )
            present: set[uuid.UUID] = set()
            for item in projections:
                if item.item_id in entities:
                    present.add(item.item_id)
                    if item.trip_id != trip_id:
                        item.trip_id = trip_id
                        item.sort_order = self._next_sort_order(user_id=user_id, trip_id=trip_id)
                        fixed += 1
                elif item.trip_id == trip_id:
                    self.db.delete(item)
                    removed += 1

            for entity_id in entities:
                if entity_id in present:
                    continue
                self.db.add(
                    TripItem(
                        user_id=user_id,
                        trip_id=trip_id,
                        item_type=item_type,
                        item_id=entity_id,
                        sort_order=self._next_sort_order(user_id=user_id, trip_id=trip_id),
                    )
                )
                self.db.flush()
                added += 1

        self.db.commit()
        return {"added": added, "fixed": fixed, "removed": removed}

    def set_order(
        self, *, user_id: uuid.UUID, trip_id: uuid.UUID, item_ids: list[uuid.UUID]
    ) -> None:
        items = {item.id: item for item in self.list_for_trip(user_id=user_id, trip_id=trip_id)}
        for index, item_id in enumerate(item_ids):
            items[item_id].sort_order = index
        self.db.commit()

    def trip_order_mode(self, *, user_id: uuid.UUID, trip_id: uuid.UUID) -> str:
        mode = self.db.scalar(
            select(Trip.timeline_order_mode).where(Trip.id == trip_id, Trip.user_id == user_id)
        )
        return mode or "chronological"
