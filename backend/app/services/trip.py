import uuid
from datetime import UTC, date, datetime
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.orm import Session

from app.models.activity import Activity
from app.models.attachment import Attachment
from app.models.expense import Expense
from app.models.hotel import Hotel
from app.models.note import Note
from app.models.transport_record import TransportRecord
from app.models.trip import Trip
from app.models.user import User
from app.repositories.activity import ActivityRepository
from app.repositories.attachment import AttachmentRepository
from app.repositories.expense import ExpenseRepository
from app.repositories.hotel import HotelRepository
from app.repositories.note import NoteRepository
from app.repositories.place import PlaceRepository
from app.repositories.transport import TransportRepository
from app.repositories.trip import TripRepository
from app.repositories.trip_item import (
    ACTIVITY_ITEM,
    HOTEL_ITEM,
    TRANSPORT_ITEM,
    TripItemRepository,
)
from app.schemas.activity import ActivityCreate, ActivityRead
from app.schemas.expense import ExpenseSummary
from app.schemas.hotel import HotelRead
from app.schemas.transport import FlightRead
from app.schemas.trip import (
    TripCreate,
    TripItemCreate,
    TripItemRead,
    TripItemUpdate,
    TripUpdate,
)
from app.services.activity import ActivityService
from app.services.expense import summarize_expenses
from app.services.expense_source import (
    SOURCE_ACTIVITY,
    SOURCE_HOTEL,
    SOURCE_TRANSPORT,
    sync_source_trip,
)
from app.services.write_lock import lock_user_writes


class TripNotFoundError(Exception):
    pass


class TripItemNotFoundError(Exception):
    pass


class InvalidTripItemTypeError(Exception):
    """The legacy add-item facade only accepts place requests; removal only
    supports the three projected types."""


class InvalidTripOrderError(Exception):
    """The supplied ordering does not match the trip's current items."""


class TimelineRepairRequiredError(Exception):
    """The trip has sources without projections; run the explicit repair first."""


def _as_utc(value: datetime | None) -> datetime | None:
    """Normalize a stored datetime for comparison (SQLite hands back naive values)."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _local_date(value: datetime, timezone: str | None, fallback: str | None) -> date:
    name = timezone or fallback or "UTC"
    try:
        zone = ZoneInfo(name)
    except ZoneInfoNotFoundError:
        zone = UTC
    return _as_utc(value).astimezone(zone).date()  # type: ignore[union-attr]


def _sort_key(
    item: TripItemRead,
    *,
    local_day: date | None,
    start: datetime | None,
    direction: Literal["asc", "desc"] = "asc",
) -> tuple:
    """Chronological ordering: day, hotels first, then instant time, then order."""
    if item.is_unscheduled:
        return (1, 0, 0, 0.0, item.sort_order, str(item.id or item.item_id))
    multiplier = -1 if direction == "desc" else 1
    day_value = (local_day.toordinal() if local_day else 0) * multiplier
    if item.time_kind == "date":
        return (0, day_value, 0, 0.0, item.sort_order, str(item.id or item.item_id))
    stamp = _as_utc(start)
    return (
        0,
        day_value,
        1,
        stamp.timestamp() * multiplier if stamp else 0.0,
        item.sort_order,
        str(item.id or item.item_id),
    )


def _group_key(item: TripItemRead, *, local_day: date | None, start: datetime | None) -> tuple:
    """Items that may be manually reordered while staying chronological."""
    if item.is_unscheduled:
        return ("unscheduled",)
    if item.time_kind == "date":
        return ("date", local_day)
    stamp = _as_utc(start)
    return ("instant", local_day, stamp)


class TripService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.trips = TripRepository(db)
        self.items = TripItemRepository(db)
        self.hotels = HotelRepository(db)
        self.places = PlaceRepository(db)
        self.activities = ActivityRepository(db)
        self.records = TransportRepository(db)
        self.expenses = ExpenseRepository(db)
        self.notes = NoteRepository(db)
        self.attachments = AttachmentRepository(db)

    def list_trips(
        self,
        *,
        user_id: uuid.UUID,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Trip], int]:
        return self.trips.list_trips(user_id=user_id, page=page, page_size=page_size)

    def get_trip(self, *, user_id: uuid.UUID, trip_id: uuid.UUID) -> Trip:
        trip = self.trips.get(user_id=user_id, trip_id=trip_id)
        if trip is None:
            raise TripNotFoundError
        return trip

    def list_records(self, *, user_id: uuid.UUID, trip_id: uuid.UUID) -> list[TransportRecord]:
        return self.trips.list_records(user_id=user_id, trip_id=trip_id)

    def list_expenses(self, *, user_id: uuid.UUID, trip_id: uuid.UUID) -> list[Expense]:
        return self.expenses.list_for_trip(user_id=user_id, trip_id=trip_id)

    def expense_summary(self, *, user_id: uuid.UUID, trip_id: uuid.UUID) -> ExpenseSummary:
        user = self.db.get(User, user_id)
        report_currency = (user.currency if user else None) or "CNY"
        return summarize_expenses(
            self.list_expenses(user_id=user_id, trip_id=trip_id),
            report_currency,
        )

    def list_notes(self, *, user_id: uuid.UUID, trip_id: uuid.UUID) -> list[Note]:
        return self.notes.list_for_trip(user_id=user_id, trip_id=trip_id)

    def list_attachments(self, *, user_id: uuid.UUID, trip_id: uuid.UUID) -> list[Attachment]:
        """Aggregate attachments of the trip's transport records (docs §8.2).

        Attachments stay owned by their source record; this view only follows
        the record's current trip. Both sides are scoped by ``user_id``.
        """
        by_resource: dict[str, list[uuid.UUID]] = {}
        for record in self.list_records(user_id=user_id, trip_id=trip_id):
            resource_type = {"flight": "flight", "train": "train", "other": "transport"}.get(
                record.type
            )
            if resource_type:
                by_resource.setdefault(resource_type, []).append(record.id)
        return self.attachments.list_for_transport_records(
            user_id=user_id, record_ids_by_resource=by_resource
        )

    # ------------------------------------------------------------------
    # timeline read model
    # ------------------------------------------------------------------
    def _load_timeline(
        self,
        *,
        user_id: uuid.UUID,
        trip_id: uuid.UUID,
        direction: Literal["asc", "desc"] = "asc",
    ) -> tuple[Trip, list[tuple[TripItemRead, tuple]]]:
        trip = self.get_trip(user_id=user_id, trip_id=trip_id)
        user = self.db.get(User, user_id)
        fallback_tz = user.timezone if user else None

        records = {
            record.id: record for record in self.list_records(user_id=user_id, trip_id=trip_id)
        }
        hotels = {
            hotel.id: hotel for hotel in self.hotels.list_for_trip(user_id=user_id, trip_id=trip_id)
        }
        activities = {
            activity.id: activity
            for activity in self.activities.list_for_trip(user_id=user_id, trip_id=trip_id)
        }

        projections = self.items.list_for_trip(user_id=user_id, trip_id=trip_id)

        presented: list[tuple[TripItemRead, tuple]] = []
        seen: set[tuple[str, uuid.UUID]] = set()

        for projection in projections:
            key = (projection.item_type, projection.item_id)
            if key in seen:
                continue
            entry = self._present_projection(
                projection=projection,
                user_id=user_id,
                records=records,
                hotels=hotels,
                activities=activities,
                fallback_tz=fallback_tz,
            )
            if entry is None:
                continue
            seen.add(key)
            presented.append(entry)

        # Sources without a projection still belong to the trip. Show them so a
        # missing self-heal row never hides real data; the explicit repair adds
        # the stable row back.
        fallback_order = len(projections)
        for record in records.values():
            if (TRANSPORT_ITEM, record.id) in seen:
                continue
            item = self._present_transport(record, item_id=None, sort_order=fallback_order)
            fallback_order += 1
            presented.append((item, self._group_for(item, fallback_tz)))
        for hotel in hotels.values():
            if (HOTEL_ITEM, hotel.id) in seen:
                continue
            item = self._present_hotel(hotel, item_id=None, sort_order=fallback_order)
            fallback_order += 1
            presented.append((item, self._group_for(item, fallback_tz)))
        for activity in activities.values():
            if (ACTIVITY_ITEM, activity.id) in seen:
                continue
            item = self._present_activity(activity, item_id=None, sort_order=fallback_order)
            fallback_order += 1
            presented.append((item, self._group_for(item, fallback_tz)))

        if trip.timeline_order_mode == "manual":
            presented.sort(
                key=lambda entry: (
                    entry[0].is_unscheduled,
                    entry[0].sort_order,
                    str(entry[0].id or entry[0].item_id),
                )
            )
        else:
            presented.sort(
                key=lambda entry: _sort_key(
                    entry[0],
                    local_day=(
                        entry[0].start_date
                        if entry[0].time_kind == "date"
                        else _local_date(entry[0].start_at, entry[0].timezone, fallback_tz)
                        if entry[0].start_at
                        else None
                    ),
                    start=entry[0].start_at,
                    direction=direction,
                )
            )

        # Expose the display index as sort_order. In manual mode the persisted
        # order is already the display order, so the value is unchanged.
        result: list[tuple[TripItemRead, tuple]] = []
        for index, (item, group) in enumerate(presented):
            updated = item.model_copy(update={"sort_order": index})
            result.append((updated, group))
        return trip, result

    def list_items(
        self, *, user_id: uuid.UUID, trip_id: uuid.UUID, direction: Literal["asc", "desc"] = "asc"
    ) -> list[TripItemRead]:
        """Return the timeline in display order. Read-only: never self-heals."""
        _, entries = self._load_timeline(user_id=user_id, trip_id=trip_id, direction=direction)
        return [entry for entry, _ in entries]

    def _group_for(self, item: TripItemRead, fallback_tz: str | None) -> tuple:
        if item.time_kind == "date":
            return _group_key(item, local_day=item.start_date, start=None)
        start = item.start_at
        local_day = _local_date(start, item.timezone, fallback_tz) if start else None
        return _group_key(item, local_day=local_day, start=start)

    def _present_projection(
        self,
        *,
        projection,
        user_id: uuid.UUID,
        records: dict,
        hotels: dict,
        activities: dict,
        fallback_tz: str | None,
    ) -> tuple[TripItemRead, tuple] | None:
        if projection.item_type == TRANSPORT_ITEM:
            record = records.get(projection.item_id)
            if record is None:
                return None
            item = self._present_transport(
                record, item_id=projection.id, sort_order=projection.sort_order
            )
        elif projection.item_type == HOTEL_ITEM:
            hotel = hotels.get(projection.item_id)
            if hotel is None:
                return None
            item = self._present_hotel(
                hotel, item_id=projection.id, sort_order=projection.sort_order
            )
        elif projection.item_type == ACTIVITY_ITEM:
            activity = activities.get(projection.item_id)
            if activity is None:
                return None
            item = self._present_activity(
                activity, item_id=projection.id, sort_order=projection.sort_order
            )
        else:
            return None

        # A projection whose source belongs to another trip is stale; hide it.
        if (
            item.item_type == TRANSPORT_ITEM
            and item.record
            and item.record.trip_id != projection.trip_id
        ):
            return None
        if item.item_type == HOTEL_ITEM and item.hotel and item.hotel.trip_id != projection.trip_id:
            return None
        if (
            item.item_type == ACTIVITY_ITEM
            and item.activity
            and item.activity.trip_id != projection.trip_id
        ):
            return None
        return item, self._group_for(item, fallback_tz)

    @staticmethod
    def _present_transport(
        record: TransportRecord, *, item_id: uuid.UUID | None, sort_order: int
    ) -> TripItemRead:
        return TripItemRead(
            id=item_id,
            item_type=TRANSPORT_ITEM,
            item_id=record.id,
            sort_order=sort_order,
            time_kind="instant",
            start_at=record.departure_time,
            end_at=record.arrival_time,
            timezone=record.departure_timezone,
            is_unscheduled=record.departure_time is None,
            record=FlightRead.model_validate(record, from_attributes=True),
        )

    @staticmethod
    def _present_hotel(hotel: Hotel, *, item_id: uuid.UUID | None, sort_order: int) -> TripItemRead:
        return TripItemRead(
            id=item_id,
            item_type=HOTEL_ITEM,
            item_id=hotel.id,
            sort_order=sort_order,
            time_kind="date",
            start_date=hotel.check_in,
            end_date=hotel.check_out,
            is_unscheduled=False,
            hotel=HotelRead.model_validate(hotel, from_attributes=True),
        )

    @staticmethod
    def _present_activity(
        activity: Activity, *, item_id: uuid.UUID | None, sort_order: int
    ) -> TripItemRead:
        return TripItemRead(
            id=item_id,
            item_type=ACTIVITY_ITEM,
            item_id=activity.id,
            sort_order=sort_order,
            time_kind="instant",
            start_at=activity.start_at,
            end_at=activity.end_at,
            timezone=activity.timezone,
            is_unscheduled=activity.start_at is None,
            activity=ActivityRead.model_validate(activity, from_attributes=True),
        )

    # ------------------------------------------------------------------
    # timeline writes
    # ------------------------------------------------------------------
    def add_item(
        self,
        *,
        user_id: uuid.UUID,
        trip_id: uuid.UUID,
        payload: TripItemCreate,
        idempotency_key: str | None = None,
        commit: bool = True,
    ) -> tuple[TripItemRead, bool]:
        """Create a visit Activity for a place (legacy add-item facade, spec #16)."""
        lock_user_writes(self.db, user_id)
        self.get_trip(user_id=user_id, trip_id=trip_id)
        if payload.item_type != "place":
            raise InvalidTripItemTypeError
        place = self.places.get(user_id=user_id, place_id=payload.item_id)
        if place is None:
            raise TripItemNotFoundError
        activity, replayed = ActivityService(self.db).create_activity_idempotent(
            user_id=user_id,
            payload=ActivityCreate(
                name=place.name,
                type="visit",
                place_id=place.id,
                start_at=payload.start_at,
                end_at=payload.end_at,
                trip_id=trip_id,
            ),
            idempotency_key=idempotency_key,
            idempotency_operation="add_place_to_trip",
            commit=commit,
        )
        projection = self.items.get_for_activity(user_id=user_id, activity_id=activity.id)
        item = self._present_activity(
            activity,
            item_id=projection.id if projection is not None else None,
            sort_order=projection.sort_order if projection is not None else 0,
        )
        return item, replayed

    def remove_item(
        self, *, user_id: uuid.UUID, trip_id: uuid.UUID, item_id: uuid.UUID, commit: bool = True
    ) -> None:
        """Remove a source record from a trip without deleting the record."""
        lock_user_writes(self.db, user_id)
        self.get_trip(user_id=user_id, trip_id=trip_id)
        item = self.items.get(user_id=user_id, trip_id=trip_id, item_id=item_id)
        if item is None:
            raise TripItemNotFoundError

        if item.item_type == TRANSPORT_ITEM:
            record = self.records.get(user_id=user_id, record_id=item.item_id)
            if record is not None and record.trip_id == trip_id:
                record.trip_id = None
                self.db.flush()
                sync_source_trip(
                    self.db,
                    user_id=user_id,
                    source_type=SOURCE_TRANSPORT,
                    source_id=item.item_id,
                    trip_id=None,
                )
        elif item.item_type == HOTEL_ITEM:
            hotel = self.hotels.get(user_id=user_id, hotel_id=item.item_id)
            if hotel is not None and hotel.trip_id == trip_id:
                hotel.trip_id = None
                self.db.flush()
                sync_source_trip(
                    self.db,
                    user_id=user_id,
                    source_type=SOURCE_HOTEL,
                    source_id=item.item_id,
                    trip_id=None,
                )
        elif item.item_type == ACTIVITY_ITEM:
            activity = self.activities.get(user_id=user_id, activity_id=item.item_id)
            if activity is not None and activity.trip_id == trip_id:
                activity.trip_id = None
                self.db.flush()
                sync_source_trip(
                    self.db,
                    user_id=user_id,
                    source_type=SOURCE_ACTIVITY,
                    source_id=item.item_id,
                    trip_id=None,
                )
        else:
            raise InvalidTripItemTypeError

        self.items.delete_item(item)
        if commit:
            self.db.commit()

    def reorder_items(
        self,
        *,
        user_id: uuid.UUID,
        trip_id: uuid.UUID,
        item_ids: list[uuid.UUID],
        commit: bool = True,
    ) -> None:
        lock_user_writes(self.db, user_id)
        trip, entries = self._load_timeline(user_id=user_id, trip_id=trip_id)
        current_ids = [entry.id for entry, _ in entries]
        if any(item_id is None for item_id in current_ids):
            raise TimelineRepairRequiredError
        if len(item_ids) != len(set(item_ids)) or set(item_ids) != set(current_ids):
            raise InvalidTripOrderError

        if trip.timeline_order_mode != "manual":
            groups_by_id = {entry.id: group for entry, group in entries}
            if [groups_by_id[item_id] for item_id in item_ids] != [group for _, group in entries]:
                raise InvalidTripOrderError
        elif [entry.is_unscheduled for entry, _ in entries] != [
            {entry.id: entry.is_unscheduled for entry, _ in entries}[item_id]
            for item_id in item_ids
        ]:
            raise InvalidTripOrderError

        self.items.set_order(user_id=user_id, trip_id=trip_id, item_ids=item_ids, commit=commit)

    def update_item(
        self,
        *,
        user_id: uuid.UUID,
        trip_id: uuid.UUID,
        item_id: uuid.UUID,
        payload: TripItemUpdate,
        commit: bool = True,
    ) -> None:
        """Move one item to a new display position. Times are source-owned."""
        lock_user_writes(self.db, user_id)
        self.get_trip(user_id=user_id, trip_id=trip_id)
        item = self.items.get(user_id=user_id, trip_id=trip_id, item_id=item_id)
        if item is None:
            raise TripItemNotFoundError
        if "sort_order" not in payload.model_fields_set:
            return
        if payload.sort_order is None:
            raise InvalidTripOrderError

        _, entries = self._load_timeline(user_id=user_id, trip_id=trip_id)
        ids = [entry.id for entry, _ in entries]
        if any(entry_id is None for entry_id in ids):
            raise TimelineRepairRequiredError
        if item_id not in ids:
            raise TripItemNotFoundError
        ids.remove(item_id)
        if payload.sort_order > len(ids):
            raise InvalidTripOrderError
        index = payload.sort_order
        ids.insert(index, item_id)
        self.reorder_items(user_id=user_id, trip_id=trip_id, item_ids=ids, commit=commit)

    def repair_timeline(
        self, *, user_id: uuid.UUID, trip_id: uuid.UUID, commit: bool = True
    ) -> dict[str, int]:
        lock_user_writes(self.db, user_id)
        self.get_trip(user_id=user_id, trip_id=trip_id)
        return self.items.repair_timeline(user_id=user_id, trip_id=trip_id, commit=commit)

    def prepare_trip(self, *, user_id: uuid.UUID, payload: TripCreate) -> Trip:
        """Build an unsaved trip (shared with the v2 importer)."""
        return Trip(user_id=user_id, **payload.model_dump())

    def create_trip(self, *, user_id: uuid.UUID, payload: TripCreate, commit: bool = True) -> Trip:
        return self.trips.create(self.prepare_trip(user_id=user_id, payload=payload), commit=commit)

    def update_trip(
        self,
        *,
        user_id: uuid.UUID,
        trip_id: uuid.UUID,
        payload: TripUpdate,
        commit: bool = True,
        direction: Literal["asc", "desc"] = "asc",
    ) -> Trip:
        lock_user_writes(self.db, user_id)
        trip = self.get_trip(user_id=user_id, trip_id=trip_id)
        data = payload.model_dump(exclude_unset=True)
        if data.get("timeline_order_mode") == "manual" and trip.timeline_order_mode != "manual":
            _, entries = self._load_timeline(user_id=user_id, trip_id=trip_id, direction=direction)
            if any(entry.id is None for entry, _ in entries):
                raise TimelineRepairRequiredError
            projections = {
                item.id: item for item in self.items.list_for_trip(user_id=user_id, trip_id=trip_id)
            }
            for index, (entry, _) in enumerate(entries):
                projections[entry.id].sort_order = index
        for field, value in data.items():
            setattr(trip, field, value)
        return self.trips.save(trip, commit=commit)

    def delete_trip(self, *, user_id: uuid.UUID, trip_id: uuid.UUID, commit: bool = True) -> None:
        lock_user_writes(self.db, user_id)
        trip = self.get_trip(user_id=user_id, trip_id=trip_id)
        self.trips.clear_records(user_id=user_id, trip_id=trip_id)
        self.trips.delete(trip, commit=commit)
