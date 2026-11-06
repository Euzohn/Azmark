"""Import / export of user-owned records (spec #42/#43)."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from zoneinfo import ZoneInfo

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.activity import Activity
from app.models.expense import Expense
from app.models.hotel import Hotel
from app.models.import_mapping import ImportBundleMapping
from app.models.migration import PlaceVisitMapping, TimelineMigrationArchive
from app.models.note import Note
from app.models.place import Place
from app.models.transport_record import TransportRecord
from app.models.trip import Trip
from app.models.trip_item import TripItem
from app.models.user import User
from app.schemas.activity import ActivityCreate
from app.schemas.data_transfer import (
    ImportDuplicate,
    ImportPreview,
    ImportResult,
    ImportRowError,
)
from app.schemas.expense import ExpenseCreate
from app.schemas.hotel import HotelCreate
from app.schemas.note import NoteCreate
from app.schemas.place import PlaceCreate
from app.schemas.status import normalize_record_status, normalize_trip_status
from app.schemas.transport import FlightCreate, OtherTransportCreate, TrainCreate
from app.schemas.trip import TripCreate
from app.services.activity import ActivityService
from app.services.dedup import iso_full, record_signature, record_signature_from_model
from app.services.expense import ExpenseService
from app.services.hotel import HotelService
from app.services.note import NoteService
from app.services.place import PlaceService
from app.services.transport import FlightService, OtherTransportService, TrainService
from app.services.trip import TripService

EXPORT_VERSION = 2
PREVIEW_ROW_LIMIT = 200

# Canonical, non-sensitive export/import columns (mirrors TransportRecord).
RECORD_FIELDS: tuple[str, ...] = (
    "type",
    "status",
    "departure_time",
    "arrival_time",
    "actual_departure_time",
    "actual_arrival_time",
    "departure_timezone",
    "arrival_timezone",
    "origin",
    "destination",
    "carrier",
    "airline_code",
    "service_number",
    "cabin_class",
    "seat",
    "departure_terminal",
    "departure_gate",
    "arrival_terminal",
    "arrival_gate",
    "check_in_desk",
    "baggage_belt",
    "aircraft_model",
    "aircraft_reg",
    "train_type",
    "carriage",
    "seat_type",
    "ticket_type",
    "vehicle_type",
    "price",
    "currency",
    "distance",
    "notes",
    "trip_name",
)

# Sensitive values (spec #45/#96): only exported/imported when the user opts in,
# and always stored encrypted via the transport service.
SENSITIVE_FIELDS: tuple[str, ...] = (
    "booking_reference",
    "ticket_number",
    "purchase_credential",
)

# Accommodation is a separate entity (spec #17), so it gets its own column set.
# It has no timezones: check-in/out are plain dates.
HOTEL_FIELDS: tuple[str, ...] = (
    "hotel",
    "status",
    "check_in",
    "check_out",
    "room_type",
    "room_number",
    "price",
    "currency",
    "address",
    "notes",
    "trip_name",
)

HOTEL_SENSITIVE_FIELDS: tuple[str, ...] = ("booking_reference",)

EXPENSE_FIELDS: tuple[str, ...] = (
    "category",
    "amount",
    "currency",
    "converted_amount",
    "converted_currency",
    "exchange_rate",
    "exchange_rate_date",
    "occurred_at",
    "description",
    "trip_name",
)

NOTE_FIELDS: tuple[str, ...] = (
    "title",
    "content",
    "trip_name",
    "created_at",
    "updated_at",
)

DATETIME_FIELDS = {
    "departure_time",
    "arrival_time",
    "actual_departure_time",
    "actual_arrival_time",
}
DECIMAL_FIELDS = {"price", "distance"}
TRIP_FIELDS = (
    "name",
    "description",
    "start_date",
    "end_date",
    "cover_image",
    "origin",
    "destination",
    "status",
)

CREATE_BY_TYPE = {
    "flight": FlightCreate,
    "train": TrainCreate,
    "other": OtherTransportCreate,
}
SERVICE_BY_TYPE = {
    "flight": FlightService,
    "train": TrainService,
    "other": OtherTransportService,
}

# v2 import dependency order (docs §10.6). Trip/Place first, then the entities
# that reference them, then spend/notes, and finally the timeline projection.
V2_ENTITY_ORDER: tuple[tuple[str, str], ...] = (
    ("trip", "trips"),
    ("place", "places"),
    ("transport", "records"),
    ("hotel", "hotels"),
    ("activity", "activities"),
    ("expense", "expenses"),
    ("note", "notes"),
    ("trip_item", "trip_items"),
    # Migration evidence travels after the entities it references. Archives
    # keep historical ids but remap any still-existing trip/place/activity.
    ("timeline_archive", "timeline_archives"),
    ("place_visit_mapping", "place_visit_mappings"),
)

V2_MODEL_BY_TYPE = {
    "trip": Trip,
    "place": Place,
    "transport": TransportRecord,
    "hotel": Hotel,
    "activity": Activity,
    "expense": Expense,
    "note": Note,
    "trip_item": TripItem,
    "timeline_archive": TimelineMigrationArchive,
    "place_visit_mapping": PlaceVisitMapping,
}

# Metadata rows are restored for audit continuity but are not user-visible
# records, so they do not inflate the "imported" counters.
V2_METADATA_TYPES = frozenset({"timeline_archive", "place_visit_mapping"})

EXPENSE_SOURCE_TYPES = ("transport", "hotel", "activity")

# v1 JSON only restores trips and transport records. These arrays exist in the
# newer bundle shape and would otherwise be dropped silently (docs §10.6).
V1_IGNORED_ARRAYS = (
    "hotels",
    "expenses",
    "notes",
    "places",
    "activities",
    "trip_items",
    "timeline_archives",
    "place_visit_mappings",
)

# Case-insensitive source header -> canonical field. Unknown headers are ignored.
FIELD_ALIASES: dict[str, str] = {
    "from": "origin",
    "from_airport": "origin",
    "from_city": "origin",
    "origin_airport": "origin",
    "departure_place": "origin",
    "departure_airport": "origin",
    "departure_station": "origin",
    "to": "destination",
    "to_airport": "destination",
    "to_city": "destination",
    "destination_airport": "destination",
    "arrival_place": "destination",
    "arrival_airport": "destination",
    "arrival_station": "destination",
    "date": "departure_time",
    "departure_date": "departure_time",
    "dep_time": "departure_time",
    "takeoff": "departure_time",
    "arrival_date": "arrival_time",
    "arr_time": "arrival_time",
    "landing": "arrival_time",
    "airline": "carrier",
    "operator": "carrier",
    "company": "carrier",
    "flight_no": "service_number",
    "flight_number": "service_number",
    "train_no": "service_number",
    "train_number": "service_number",
    "number": "service_number",
    "pnr": "booking_reference",
    "booking": "booking_reference",
    "booking_ref": "booking_reference",
    "confirmation": "booking_reference",
    "ticket": "ticket_number",
    "ticket_no": "ticket_number",
    "class": "cabin_class",
    "cabin": "cabin_class",
    "trip": "trip_name",
    "kind": "type",
    "transport": "type",
    "transport_type": "type",
    "cost": "price",
    "amount": "price",
    "km": "distance",
}


def _norm_header(value: str) -> str:
    return value.strip().lower().replace(" ", "_").replace("-", "_")


def parse_datetime(raw: Any, tz_name: str | None = None) -> datetime | None:
    """Lenient ISO / common formats. Naive values are assumed UTC unless a tz is named."""
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    value: datetime
    try:
        value = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        parsed = None
        for fmt in (
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d",
            "%Y/%m/%d %H:%M:%S",
            "%Y/%m/%d %H:%M",
            "%Y/%m/%d",
            "%d/%m/%Y %H:%M",
            "%d/%m/%Y",
        ):
            try:
                parsed = datetime.strptime(text, fmt)
                break
            except ValueError:
                continue
        if parsed is None:
            raise ValueError("unrecognized datetime") from None
        value = parsed
    if value.tzinfo is None:
        if tz_name:
            try:
                value = value.replace(tzinfo=ZoneInfo(tz_name)).astimezone(UTC)
            except Exception:
                value = value.replace(tzinfo=UTC)
        else:
            value = value.replace(tzinfo=UTC)
    return value


def parse_date(raw: Any) -> date | None:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        try:
            return datetime.strptime(text, "%Y/%m/%d").date()
        except ValueError:
            raise ValueError("unrecognized date") from None


def normalize_type(raw: Any) -> str:
    value = str(raw or "").strip().lower()
    if value in {"flight", "plane", "airplane", "air"}:
        return "flight"
    if value in {"train", "rail", "railway"}:
        return "train"
    if value in {"other", "bus", "ferry", "taxi", "car", "coach", "boat", "ship"}:
        return "other"
    return "flight"  # default when missing/unknown


class DataTransferService:
    """Export all / import preview & commit, fully user-scoped (spec #42/#43/#57)."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ---------------- export ----------------
    def _export_record(
        self, record: TransportRecord, include_sensitive: bool, trip_names: dict[uuid.UUID, str]
    ) -> dict[str, Any]:
        data: dict[str, Any] = {}
        for field in RECORD_FIELDS:
            value = (
                getattr(record, field, None)
                if field != "trip_name"
                else trip_names.get(record.trip_id)
            )
            if field in DATETIME_FIELDS:
                data[field] = iso_full(value)
            elif isinstance(value, Decimal):
                data[field] = float(value)
            else:
                data[field] = value
        if include_sensitive:
            for field in SENSITIVE_FIELDS:
                data[field] = getattr(record, field, None)
        return data

    # -- v2 export (stable ids + relations by id, docs §10.6) -----------------

    @staticmethod
    def _dec(value: Decimal | None) -> str | None:
        """Money/distance round-trips as a decimal string, never a float."""
        return str(value) if value is not None else None

    def _export_record_v2(self, record: TransportRecord, include_sensitive: bool) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": str(record.id),
            "trip_id": str(record.trip_id) if record.trip_id else None,
        }
        for field in RECORD_FIELDS:
            if field == "trip_name":
                continue
            value = getattr(record, field, None)
            if field in DATETIME_FIELDS:
                data[field] = iso_full(value) if value else None
            elif isinstance(value, Decimal):
                data[field] = self._dec(value)
            else:
                data[field] = value
        if include_sensitive:
            for field in SENSITIVE_FIELDS:
                data[field] = getattr(record, field, None)
        return data

    def _export_hotel_v2(self, hotel: Hotel, include_sensitive: bool) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": str(hotel.id),
            "trip_id": str(hotel.trip_id) if hotel.trip_id else None,
        }
        for field in HOTEL_FIELDS:
            if field == "trip_name":
                continue
            value = getattr(hotel, field, None)
            if field in ("check_in", "check_out"):
                data[field] = value.isoformat() if value else None
            elif isinstance(value, Decimal):
                data[field] = self._dec(value)
            else:
                data[field] = value
        # Coordinates are part of the map state, not a derived value.
        data["lat"] = hotel.lat
        data["lon"] = hotel.lon
        if include_sensitive:
            for field in HOTEL_SENSITIVE_FIELDS:
                data[field] = getattr(hotel, field, None)
        return data

    def _export_expense_v2(self, expense: Expense) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": str(expense.id),
            "trip_id": str(expense.trip_id) if expense.trip_id else None,
            "source_type": expense.source_type,
            "source_id": str(expense.source_id) if expense.source_id else None,
        }
        for field in EXPENSE_FIELDS:
            if field == "trip_name":
                continue
            value = getattr(expense, field, None)
            if field == "exchange_rate_date":
                data[field] = value.isoformat() if value else None
            elif field == "occurred_at":
                data[field] = iso_full(value) if value else None
            elif isinstance(value, Decimal):
                data[field] = self._dec(value)
            else:
                data[field] = value
        return data

    def _export_note_v2(self, note: Note) -> dict[str, Any]:
        return {
            "id": str(note.id),
            "trip_id": str(note.trip_id) if note.trip_id else None,
            "title": note.title,
            "content": note.content,
            "created_at": iso_full(note.created_at),
            "updated_at": iso_full(note.updated_at),
        }

    def _export_activity_v2(self, activity: Activity) -> dict[str, Any]:
        return {
            "id": str(activity.id),
            "trip_id": str(activity.trip_id) if activity.trip_id else None,
            "place_id": str(activity.place_id) if activity.place_id else None,
            "name": activity.name,
            "type": activity.type,
            "start_at": iso_full(activity.start_at) if activity.start_at else None,
            "end_at": iso_full(activity.end_at) if activity.end_at else None,
            "timezone": activity.timezone,
            "price": self._dec(activity.price),
            "currency": activity.currency,
            "notes": activity.notes,
        }

    def _export_trip_v2(self, trip: Trip) -> dict[str, Any]:
        return {
            "id": str(trip.id),
            "name": trip.name,
            "description": trip.description,
            "start_date": trip.start_date.isoformat() if trip.start_date else None,
            "end_date": trip.end_date.isoformat() if trip.end_date else None,
            "cover_image": trip.cover_image,
            "origin": trip.origin,
            "destination": trip.destination,
            "status": trip.status,
            "timeline_order_mode": trip.timeline_order_mode,
        }

    def _export_trip_item_v2(self, item: TripItem) -> dict[str, Any]:
        return {
            "id": str(item.id),
            "trip_id": str(item.trip_id),
            "item_type": item.item_type,
            "item_id": str(item.item_id),
            "sort_order": item.sort_order,
        }

    def _export_timeline_archive_v2(self, archive: TimelineMigrationArchive) -> dict[str, Any]:
        return {
            "id": str(archive.id),
            "migration_key": archive.migration_key,
            "original_item_id": str(archive.original_item_id),
            "trip_id": str(archive.trip_id) if archive.trip_id else None,
            "item_type": archive.item_type,
            "item_id": str(archive.item_id) if archive.item_id else None,
            "start_at": iso_full(archive.start_at) if archive.start_at else None,
            "end_at": iso_full(archive.end_at) if archive.end_at else None,
            "sort_order": archive.sort_order,
            "source_start_at": (
                iso_full(archive.source_start_at) if archive.source_start_at else None
            ),
            "source_end_at": iso_full(archive.source_end_at) if archive.source_end_at else None,
            "diff_type": archive.diff_type,
            "status": archive.status,
            "user_choice": archive.user_choice,
            "created_at": iso_full(archive.created_at),
        }

    def _export_place_visit_mapping_v2(self, mapping: PlaceVisitMapping) -> dict[str, Any]:
        return {
            "id": str(mapping.id),
            "migration_key": mapping.migration_key,
            "original_item_id": str(mapping.original_item_id),
            "activity_id": str(mapping.activity_id),
            "created_at": iso_full(mapping.created_at),
        }

    def export_json(self, *, user_id: uuid.UUID, include_sensitive: bool = False) -> str:
        records = self._all_records(user_id)
        trips = self._all_trips(user_id)
        user = self.db.get(User, user_id)
        bundle = {
            "version": EXPORT_VERSION,
            "bundle_id": str(uuid.uuid4()),
            "exported_at": datetime.now(UTC).isoformat(),
            "include_sensitive": include_sensitive,
            "settings": {
                "display_name": user.display_name if user else None,
                "email": user.email if user else None,
                "locale": user.locale if user else None,
                "timezone": user.timezone if user else None,
                "currency": user.currency if user else None,
            },
            "trips": [self._export_trip_v2(t) for t in trips],
            "records": [self._export_record_v2(r, include_sensitive) for r in records],
            "hotels": [
                self._export_hotel_v2(h, include_sensitive) for h in self._all_hotels(user_id)
            ],
            "expenses": [self._export_expense_v2(e) for e in self._all_expenses(user_id)],
            "notes": [self._export_note_v2(n) for n in self._all_notes(user_id)],
            "places": [self._export_place(p) for p in self._all_places(user_id)],
            "activities": [self._export_activity_v2(a) for a in self._all_activities(user_id)],
            "trip_items": [self._export_trip_item_v2(i) for i in self._all_trip_items(user_id)],
            "timeline_archives": [
                self._export_timeline_archive_v2(a) for a in self._all_timeline_archives(user_id)
            ],
            "place_visit_mappings": [
                self._export_place_visit_mapping_v2(m)
                for m in self._all_place_visit_mappings(user_id)
            ],
        }
        return json.dumps(bundle, ensure_ascii=False, indent=2)

    def export_csv(self, *, user_id: uuid.UUID, include_sensitive: bool = False) -> str:
        records = self._all_records(user_id)
        trip_names = {trip.id: trip.name for trip in self._all_trips(user_id)}
        columns = list(RECORD_FIELDS)
        if include_sensitive:
            columns += list(SENSITIVE_FIELDS)
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=columns)
        writer.writeheader()
        for record in records:
            writer.writerow(self._export_record(record, include_sensitive, trip_names))
        return buffer.getvalue()

    def template(self, *, format: str) -> str:
        columns = list(RECORD_FIELDS)
        sample = {
            "type": "flight",
            "status": "scheduled",
            "departure_time": "2026-08-01T08:00:00+08:00",
            "arrival_time": "2026-08-01T11:30:00+08:00",
            "departure_timezone": "Asia/Shanghai",
            "arrival_timezone": "Asia/Shanghai",
            "origin": "PEK",
            "destination": "SFO",
            "carrier": "Air China",
            "airline_code": "CA",
            "service_number": "CA985",
            "price": 5200.50,
            "currency": "CNY",
            "trip_name": "Summer 2026",
        }
        if format == "csv":
            buffer = io.StringIO()
            writer = csv.DictWriter(buffer, fieldnames=columns)
            writer.writeheader()
            writer.writerow(sample)
            return buffer.getvalue()
        return json.dumps(
            {"version": 1, "trips": [], "records": [sample]},
            ensure_ascii=False,
            indent=2,
        )

    # ---------------- import ----------------
    def preview(
        self,
        *,
        user_id: uuid.UUID,
        format: str,
        content: str,
        mapping: dict[str, str] | None = None,
    ) -> ImportPreview:
        bundle = self._load_v2_bundle(format, content)
        if bundle is not None:
            return self._preview_v2(user_id, bundle)
        columns, raw_rows, trips = self._parse(format, content)
        field_mapping = self._resolve_mapping(columns, mapping)
        existing = {record_signature_from_model(r) for r in self._all_records(user_id)}
        errors: list[ImportRowError] = []
        duplicates: list[ImportDuplicate] = []
        rows: list[dict[str, Any]] = []
        valid = 0
        for index, raw in enumerate(raw_rows, start=2):
            normalized, row_errors = self._normalize_row(raw, field_mapping)
            row_number = index
            for field, message in row_errors:
                errors.append(ImportRowError(row=row_number, field=field, message=message))
            if row_errors:
                continue
            sig = record_signature(record_type=normalized.get("type", "flight"), payload=normalized)
            if sig in existing:
                duplicates.append(ImportDuplicate(row=row_number, signature=sig))
                continue
            rows.append(self._json_safe(normalized))
            valid += 1
        truncated = len(rows) > PREVIEW_ROW_LIMIT
        return ImportPreview(
            format=format,
            columns=columns,
            field_mapping=field_mapping,
            target_fields=[*RECORD_FIELDS, *SENSITIVE_FIELDS],
            total=len(raw_rows),
            valid=min(valid, PREVIEW_ROW_LIMIT),
            duplicate_count=len(duplicates),
            error_count=len(errors),
            errors=errors,
            duplicates=duplicates,
            rows=rows[:PREVIEW_ROW_LIMIT],
            truncated=truncated,
            warnings=self._v1_warnings(format, content),
        )

    def import_records(
        self,
        *,
        user_id: uuid.UUID,
        format: str,
        content: str,
        mapping: dict[str, str] | None = None,
    ) -> ImportResult:
        bundle = self._load_v2_bundle(format, content)
        if bundle is not None:
            return self._import_v2(user_id, bundle)
        columns, raw_rows, trips = self._parse(format, content)
        field_mapping = self._resolve_mapping(columns, mapping)

        normalized_rows: list[tuple[int, dict[str, Any], list[tuple[str | None, str]]]] = []
        for index, raw in enumerate(raw_rows, start=2):
            normalized, row_errors = self._normalize_row(raw, field_mapping)
            normalized_rows.append((index, normalized, row_errors))

        # Trips may come from a JSON bundle or be named by a record's trip column.
        trip_specs = list(trips)
        known_names = {str(t.get("name")).strip() for t in trip_specs if t.get("name")}
        for _, normalized, row_errors in normalized_rows:
            name = normalized.get("trip_name")
            if row_errors or not name or name in known_names:
                continue
            trip_specs.append({"name": name})
            known_names.add(name)
        trip_ids, trips_created = self._ensure_trips(user_id, trip_specs)

        existing = {record_signature_from_model(r) for r in self._all_records(user_id)}
        imported = skipped = failed = 0
        errors: list[ImportRowError] = []
        for index, normalized, row_errors in normalized_rows:
            if row_errors:
                for field, message in row_errors:
                    errors.append(ImportRowError(row=index, field=field, message=message))
                failed += 1
                continue
            sig = record_signature(record_type=normalized.get("type", "flight"), payload=normalized)
            if sig in existing:
                skipped += 1
                continue
            try:
                self._create_record(user_id, normalized, trip_ids)
                existing.add(sig)
                imported += 1
            except (ValidationError, ValueError) as exc:
                errors.append(
                    ImportRowError(row=index, field=None, message=str(exc).splitlines()[0][:300])
                )
                failed += 1
        return ImportResult(
            imported=imported,
            skipped_duplicates=skipped,
            failed=failed,
            trips_created=trips_created,
            errors=errors[:200],
        )

    # ---------------- v2 import (docs §10.6) ----------------
    def _load_v2_bundle(self, format: str, content: str) -> dict[str, Any] | None:
        """Return a v2 bundle, or ``None`` when the payload is the legacy v1 shape."""
        if format != "json":
            return None
        try:
            data = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON: {exc}") from None
        if not isinstance(data, dict):
            return None
        raw_version = data.get("version", 1)
        try:
            version = int(raw_version)
        except (TypeError, ValueError):
            raise ValueError("unsupported export version") from None
        if version < 2:
            return None
        if version > EXPORT_VERSION:
            raise ValueError(f"unsupported export version {version}")
        return data

    def _v1_warnings(self, format: str, content: str) -> list[str]:
        """Tell the user which newer arrays a v1 JSON import will ignore."""
        if format != "json":
            return []
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            return []
        if not isinstance(data, dict):
            return []
        try:
            if int(data.get("version", 1)) >= 2:
                return []
        except (TypeError, ValueError):
            return []
        warnings: list[str] = []
        for key in V1_IGNORED_ARRAYS:
            rows = data.get(key)
            if isinstance(rows, list) and rows:
                warnings.append(
                    f"v1 import ignores '{key}' ({len(rows)} rows); use a v2 export to restore it"
                )
        return warnings

    def _v2_sections(self, bundle: dict[str, Any]) -> dict[str, Any]:
        bundle_id = bundle.get("bundle_id")
        if not isinstance(bundle_id, str) or not bundle_id.strip():
            raise ValueError("v2 bundle is missing bundle_id")
        entities: list[tuple[str, list[dict[str, Any]]]] = []
        for entity_type, key in V2_ENTITY_ORDER:
            raw = bundle.get(key, [])
            if raw is None:
                raw = []
            if not isinstance(raw, list):
                raise ValueError(f"'{key}' must be an array")
            items: list[dict[str, Any]] = []
            seen: set[str] = set()
            for item in raw:
                if not isinstance(item, dict):
                    raise ValueError(f"'{key}' rows must be objects")
                exported_id = self._exported_id(item, key)
                if exported_id in seen:
                    raise ValueError(f"'{key}' contains a duplicate id {exported_id}")
                seen.add(exported_id)
                items.append(item)
            entities.append((entity_type, items))
        return {"bundle_id": bundle_id, "entities": entities}

    @staticmethod
    def _exported_id(item: dict[str, Any], section: str) -> str:
        value = item.get("id")
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"'{section}' row is missing its exported id")
        try:
            uuid.UUID(value)
        except (ValueError, TypeError):
            raise ValueError(f"'{section}' row has an invalid exported id") from None
        return value

    @staticmethod
    def _content_hash(item: dict[str, Any]) -> str:
        canonical = json.dumps(item, sort_keys=True, ensure_ascii=False, default=str)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def _load_mappings(
        self, user_id: uuid.UUID, bundle_id: str
    ) -> dict[tuple[str, str], ImportBundleMapping]:
        rows = self.db.scalars(
            select(ImportBundleMapping).where(
                ImportBundleMapping.user_id == user_id,
                ImportBundleMapping.bundle_id == bundle_id,
            )
        )
        return {(row.entity_type, row.exported_id): row for row in rows}

    def _resolve_v2_ref(
        self,
        resolved: dict[tuple[str, str], uuid.UUID],
        entity_type: str,
        value: Any,
        label: str,
    ) -> uuid.UUID | None:
        if value in (None, ""):
            return None
        if not isinstance(value, str):
            raise ValueError(f"{label} must be an exported id string")
        key = (entity_type, value)
        if key not in resolved:
            raise ValueError(f"{label} {value} does not resolve to an imported {entity_type}")
        return resolved[key]

    @staticmethod
    def _resolve_v2_optional(
        resolved: dict[tuple[str, str], uuid.UUID],
        entity_type: str,
        value: Any,
    ) -> uuid.UUID | None:
        """Resolve a historical reference when its target is in this bundle."""
        if value in (None, ""):
            return None
        return resolved.get((entity_type, str(value)))

    @staticmethod
    def _historical_uuid(value: Any, label: str) -> uuid.UUID | None:
        """Keep a no-longer-existing id as an audit-only identifier (§10.6)."""
        if value in (None, ""):
            return None
        try:
            return uuid.UUID(str(value))
        except (ValueError, TypeError):
            raise ValueError(f"{label} must be a UUID") from None

    def _required_historical_uuid(self, value: Any, label: str) -> uuid.UUID:
        parsed = self._historical_uuid(value, label)
        if parsed is None:
            raise ValueError(f"{label} is required")
        return parsed

    @staticmethod
    def _namespaced_migration_key(bundle_id: str, key: Any) -> str:
        """Scope archive idempotency to one bundle, so imports never collide."""
        value = f"{bundle_id}:{key or 'import'}"
        if len(value) <= 64:
            return value
        return hashlib.sha256(value.encode("utf-8")).hexdigest()[:64]

    def _build_v2_entity(
        self,
        *,
        user_id: uuid.UUID,
        bundle_id: str,
        entity_type: str,
        item: dict[str, Any],
        resolved: dict[tuple[str, str], uuid.UUID],
        entity_trip: dict[tuple[str, uuid.UUID], uuid.UUID | None],
        place_timezones: dict[uuid.UUID, str | None],
    ) -> Any:
        new_id = uuid.uuid4()
        if entity_type == "trip":
            data = {
                "name": item.get("name"),
                "description": item.get("description"),
                "start_date": parse_date(item.get("start_date")),
                "end_date": parse_date(item.get("end_date")),
                "cover_image": item.get("cover_image"),
                "origin": item.get("origin"),
                "destination": item.get("destination"),
                "status": item.get("status") or "planned",
                "timeline_order_mode": item.get("timeline_order_mode") or "chronological",
            }
            payload = TripCreate.model_validate(data)
            trip = TripService(self.db).prepare_trip(user_id=user_id, payload=payload)
            trip.id = new_id
            return trip

        if entity_type == "place":
            data = {
                field: item.get(field)
                for field in (
                    "type",
                    "country",
                    "region",
                    "city",
                    "district",
                    "name",
                    "localized_name",
                    "lat",
                    "lon",
                    "timezone",
                    "external_ids",
                )
            }
            payload = PlaceCreate.model_validate(data)
            place = PlaceService(self.db).prepare_place(user_id=user_id, payload=payload)
            place.id = new_id
            return place

        if entity_type == "transport":
            trip_id = self._resolve_v2_ref(resolved, "trip", item.get("trip_id"), "trip_id")
            record_type = str(item.get("type") or "flight").lower()
            create_model = CREATE_BY_TYPE.get(record_type)
            service_class = SERVICE_BY_TYPE.get(record_type)
            if create_model is None or service_class is None:
                raise ValueError(f"unsupported transport type '{record_type}'")
            data = {
                field: item.get(field)
                for field in RECORD_FIELDS
                if field != "trip_name" and field in item
            }
            data["trip_id"] = trip_id
            payload = create_model.model_validate(data)
            # force=True: a restore is not a new submission, so dedup against
            # the target user's existing records must not apply.
            record = service_class(self.db).prepare_record(
                user_id=user_id, payload=payload, force=True, validate_refs=False
            )
            record.id = new_id
            return record

        if entity_type == "hotel":
            trip_id = self._resolve_v2_ref(resolved, "trip", item.get("trip_id"), "trip_id")
            data = {
                "hotel": item.get("hotel"),
                "check_in": parse_date(item.get("check_in")),
                "check_out": parse_date(item.get("check_out")),
                "room_type": item.get("room_type"),
                "room_number": item.get("room_number"),
                "booking_reference": item.get("booking_reference"),
                "price": item.get("price"),
                "currency": item.get("currency"),
                "address": item.get("address"),
                "notes": item.get("notes"),
                "trip_id": trip_id,
                "status": item.get("status") or "scheduled",
                "lat": item.get("lat"),
                "lon": item.get("lon"),
            }
            payload = HotelCreate.model_validate(data)
            hotel = HotelService(self.db).prepare_hotel(
                user_id=user_id, payload=payload, force=True, validate_refs=False, restore=True
            )
            hotel.id = new_id
            return hotel

        if entity_type == "activity":
            trip_id = self._resolve_v2_ref(resolved, "trip", item.get("trip_id"), "trip_id")
            place_id = self._resolve_v2_ref(resolved, "place", item.get("place_id"), "place_id")
            data = {
                "name": item.get("name"),
                "type": item.get("type") or "other",
                "place_id": place_id,
                "start_at": parse_datetime(item.get("start_at")),
                "end_at": parse_datetime(item.get("end_at")),
                "timezone": item.get("timezone"),
                "price": item.get("price"),
                "currency": item.get("currency"),
                "notes": item.get("notes"),
                "trip_id": trip_id,
            }
            payload = ActivityCreate.model_validate(data)
            activity = ActivityService(self.db).prepare_activity(
                user_id=user_id,
                payload=payload,
                validate_refs=False,
                place_timezone=(place_timezones.get(place_id) if place_id is not None else None),
            )
            activity.id = new_id
            return activity

        if entity_type == "expense":
            trip_id = self._resolve_v2_ref(resolved, "trip", item.get("trip_id"), "trip_id")
            source_type = item.get("source_type")
            source_id_raw = item.get("source_id")
            source_id: uuid.UUID | None = None
            if source_type is not None or source_id_raw is not None:
                if source_type not in EXPENSE_SOURCE_TYPES:
                    raise ValueError("expense source_type is unsupported")
                source_id = self._resolve_v2_ref(resolved, source_type, source_id_raw, "source_id")
                derived_trip = entity_trip.get((source_type, source_id))
                if trip_id is not None and derived_trip is not None and trip_id != derived_trip:
                    raise ValueError("expense trip_id disagrees with its source record")
                trip_id = derived_trip
            data = {
                "category": item.get("category") or "other",
                "amount": item.get("amount"),
                "currency": item.get("currency"),
                "converted_amount": item.get("converted_amount"),
                "converted_currency": item.get("converted_currency"),
                "exchange_rate": item.get("exchange_rate"),
                "exchange_rate_date": parse_date(item.get("exchange_rate_date")),
                "occurred_at": parse_datetime(item.get("occurred_at")),
                "description": item.get("description"),
                "trip_id": trip_id,
                "source_type": source_type,
                "source_id": source_id,
            }
            payload = ExpenseCreate.model_validate(data)
            # restore=True keeps a null occurred_at null instead of stamping now.
            expense = ExpenseService(self.db).prepare_expense(
                user_id=user_id, payload=payload, restore=True
            )
            expense.id = new_id
            return expense

        if entity_type == "note":
            trip_id = self._resolve_v2_ref(resolved, "trip", item.get("trip_id"), "trip_id")
            data = {
                "title": item.get("title"),
                "content": item.get("content"),
                "trip_id": trip_id,
            }
            payload = NoteCreate.model_validate(data)
            note = NoteService(self.db).prepare_note(
                user_id=user_id, payload=payload, validate_refs=False
            )
            note.id = new_id
            created_at = parse_datetime(item.get("created_at"))
            updated_at = parse_datetime(item.get("updated_at"))
            if created_at is not None:
                note.created_at = created_at
            if updated_at is not None:
                note.updated_at = updated_at
            return note

        if entity_type == "trip_item":
            trip_id = self._resolve_v2_ref(resolved, "trip", item.get("trip_id"), "trip_id")
            item_type = item.get("item_type")
            if item_type not in ("transport", "hotel", "activity"):
                raise ValueError("trip_item has an unsupported item_type")
            item_id = self._resolve_v2_ref(resolved, item_type, item.get("item_id"), "item_id")
            return TripItem(
                id=new_id,
                user_id=user_id,
                trip_id=trip_id,
                item_type=item_type,
                item_id=item_id,
                sort_order=int(item.get("sort_order") or 0),
            )

        if entity_type == "timeline_archive":
            item_type = str(item.get("item_type") or "unknown")
            raw_item_id = item.get("item_id")
            raw_trip_id = item.get("trip_id")
            mapped_item_id = self._resolve_v2_optional(resolved, item_type, raw_item_id)
            mapped_trip_id = self._resolve_v2_optional(resolved, "trip", raw_trip_id)
            archive = TimelineMigrationArchive(
                id=new_id,
                user_id=user_id,
                # Namespace the key so the same export imported as a different
                # bundle never collides with the original archive row (§10.6).
                migration_key=self._namespaced_migration_key(bundle_id, item.get("migration_key")),
                original_item_id=self._required_historical_uuid(
                    item.get("original_item_id"), "original_item_id"
                ),
                trip_id=(
                    mapped_trip_id
                    if mapped_trip_id is not None
                    else self._historical_uuid(raw_trip_id, "trip_id")
                ),
                item_type=item_type,
                item_id=(
                    mapped_item_id
                    if mapped_item_id is not None
                    else self._historical_uuid(raw_item_id, "item_id")
                ),
                start_at=parse_datetime(item.get("start_at")),
                end_at=parse_datetime(item.get("end_at")),
                sort_order=int(item.get("sort_order") or 0),
                source_start_at=parse_datetime(item.get("source_start_at")),
                source_end_at=parse_datetime(item.get("source_end_at")),
                diff_type=str(item.get("diff_type") or "unknown"),
                status=str(item.get("status") or "unknown"),
                user_choice=item.get("user_choice"),
            )
            created_at = parse_datetime(item.get("created_at"))
            if created_at is not None:
                archive.created_at = created_at
            return archive

        if entity_type == "place_visit_mapping":
            raw_activity_id = item.get("activity_id")
            mapped_activity_id = self._resolve_v2_optional(resolved, "activity", raw_activity_id)
            mapping = PlaceVisitMapping(
                id=new_id,
                user_id=user_id,
                migration_key=self._namespaced_migration_key(bundle_id, item.get("migration_key")),
                original_item_id=self._required_historical_uuid(
                    item.get("original_item_id"), "original_item_id"
                ),
                activity_id=(
                    mapped_activity_id
                    if mapped_activity_id is not None
                    else self._required_historical_uuid(raw_activity_id, "activity_id")
                ),
            )
            created_at = parse_datetime(item.get("created_at"))
            if created_at is not None:
                mapping.created_at = created_at
            return mapping

        raise ValueError(f"unsupported entity type '{entity_type}'")

    def _verify_v2_mapping(
        self,
        *,
        user_id: uuid.UUID,
        entity_type: str,
        mapping: ImportBundleMapping,
        item: dict[str, Any],
    ) -> Any:
        model = self.db.get(V2_MODEL_BY_TYPE[entity_type], mapping.target_id)
        if model is None or getattr(model, "user_id", None) != user_id:
            raise ValueError(
                f"{entity_type} {mapping.exported_id} was deleted after a previous import"
            )
        if mapping.content_hash != self._content_hash(item):
            raise ValueError(
                f"{entity_type} {mapping.exported_id} changed content under the same bundle id"
            )
        return model

    def _run_v2(
        self, user_id: uuid.UUID, bundle: dict[str, Any], *, dry_run: bool
    ) -> tuple[int, int, int, list[ImportRowError]]:
        try:
            sections = self._v2_sections(bundle)
        except ValueError as exc:
            return 0, 0, 0, [ImportRowError(row=0, field="bundle", message=str(exc))]

        bundle_id = sections["bundle_id"]
        mappings = self._load_mappings(user_id, bundle_id)
        resolved: dict[tuple[str, str], uuid.UUID] = {}
        entity_trip: dict[tuple[str, uuid.UUID], uuid.UUID | None] = {}
        place_timezones: dict[uuid.UUID, str | None] = {}
        failed: set[tuple[str, str]] = set()
        errors: list[ImportRowError] = []
        imported = skipped = trips_created = 0
        row = 0

        # Resolve existing mappings first so new rows may reference them.
        for entity_type, items in sections["entities"]:
            for item in items:
                row += 1
                key = (entity_type, self._exported_id(item, entity_type))
                mapping = mappings.get(key)
                if mapping is None:
                    continue
                try:
                    model = self._verify_v2_mapping(
                        user_id=user_id,
                        entity_type=entity_type,
                        mapping=mapping,
                        item=item,
                    )
                except ValueError as exc:
                    errors.append(ImportRowError(row=row, field=entity_type, message=str(exc)))
                    failed.add(key)
                    continue
                resolved[key] = model.id
                entity_trip[(entity_type, model.id)] = getattr(model, "trip_id", None)
                if entity_type == "place":
                    place_timezones[model.id] = model.timezone
                if entity_type not in V2_METADATA_TYPES and entity_type != "trip_item":
                    skipped += 1

        for entity_type, items in sections["entities"]:
            for item in items:
                exported_id = self._exported_id(item, entity_type)
                key = (entity_type, exported_id)
                # Do not recreate a row that failed verification under the same
                # bundle id: its mapping still exists and must not be duplicated.
                if key in resolved or key in failed:
                    continue
                try:
                    model = self._build_v2_entity(
                        user_id=user_id,
                        bundle_id=bundle_id,
                        entity_type=entity_type,
                        item=item,
                        resolved=resolved,
                        entity_trip=entity_trip,
                        place_timezones=place_timezones,
                    )
                except (ValueError, ValidationError, TypeError) as exc:
                    message = " ".join(str(exc).splitlines()[:3])[:300]
                    errors.append(ImportRowError(row=row, field=entity_type, message=message))
                    row += 1
                    continue
                resolved[key] = model.id
                entity_trip[(entity_type, model.id)] = getattr(model, "trip_id", None)
                if entity_type == "place":
                    place_timezones[model.id] = model.timezone
                if not dry_run:
                    self.db.add(model)
                    self.db.add(
                        ImportBundleMapping(
                            user_id=user_id,
                            bundle_id=bundle_id,
                            entity_type=entity_type,
                            exported_id=exported_id,
                            target_id=model.id,
                            content_hash=self._content_hash(item),
                        )
                    )
                if entity_type == "trip":
                    trips_created += 1
                elif entity_type != "trip_item" and entity_type not in V2_METADATA_TYPES:
                    imported += 1
                row += 1

        # On errors nothing is committed; the request-scoped session rollback
        # discards every pending row and mapping (docs §10.6 atomic bundle).
        return imported, skipped, trips_created, errors

    def _import_v2(self, user_id: uuid.UUID, bundle: dict[str, Any]) -> ImportResult:
        imported, skipped, trips_created, errors = self._run_v2(user_id, bundle, dry_run=False)
        if errors:
            detail = errors[0].message
            raise ValueError(f"import failed and was rolled back: {detail}")
        # A single outer commit keeps the bundle atomic (docs §10.6).
        self.db.commit()
        return ImportResult(
            imported=imported,
            skipped_duplicates=skipped,
            failed=0,
            trips_created=trips_created,
            errors=[],
        )

    def _preview_v2(self, user_id: uuid.UUID, bundle: dict[str, Any]) -> ImportPreview:
        imported, skipped, _trips, errors = self._run_v2(user_id, bundle, dry_run=True)
        try:
            total = sum(len(items) for _, items in self._v2_sections(bundle)["entities"])
        except ValueError as exc:
            return ImportPreview(
                format="json",
                columns=[],
                field_mapping={},
                target_fields=[],
                total=0,
                valid=0,
                duplicate_count=0,
                error_count=1,
                errors=[ImportRowError(row=0, field="bundle", message=str(exc))],
                duplicates=[],
                rows=[],
                truncated=False,
            )
        return ImportPreview(
            format="json",
            columns=[],
            field_mapping={},
            target_fields=[],
            total=total,
            valid=imported if not errors else 0,
            duplicate_count=skipped,
            error_count=len(errors),
            errors=errors[:200],
            duplicates=[],
            rows=[],
            truncated=False,
        )

    # ---------------- helpers ----------------
    def _all_records(self, user_id: uuid.UUID) -> list[TransportRecord]:
        return list(
            self.db.scalars(select(TransportRecord).where(TransportRecord.user_id == user_id))
        )

    def _all_trips(self, user_id: uuid.UUID) -> list[Trip]:
        return list(self.db.scalars(select(Trip).where(Trip.user_id == user_id)))

    def _all_trip_items(self, user_id: uuid.UUID) -> list[TripItem]:
        return list(
            self.db.scalars(
                select(TripItem)
                .where(TripItem.user_id == user_id)
                .order_by(TripItem.trip_id, TripItem.sort_order, TripItem.id)
            )
        )

    def _all_timeline_archives(self, user_id: uuid.UUID) -> list[TimelineMigrationArchive]:
        return list(
            self.db.scalars(
                select(TimelineMigrationArchive)
                .where(TimelineMigrationArchive.user_id == user_id)
                .order_by(TimelineMigrationArchive.created_at, TimelineMigrationArchive.id)
            )
        )

    def _all_place_visit_mappings(self, user_id: uuid.UUID) -> list[PlaceVisitMapping]:
        return list(
            self.db.scalars(
                select(PlaceVisitMapping)
                .where(PlaceVisitMapping.user_id == user_id)
                .order_by(PlaceVisitMapping.created_at, PlaceVisitMapping.id)
            )
        )

    def _all_hotels(self, user_id: uuid.UUID) -> list[Hotel]:
        return list(
            self.db.scalars(
                select(Hotel)
                .where(Hotel.user_id == user_id)
                .order_by(Hotel.check_in.asc(), Hotel.id)
            )
        )

    def _export_hotel(
        self, hotel: Hotel, include_sensitive: bool, trip_names: dict[uuid.UUID, str]
    ) -> dict[str, Any]:
        data: dict[str, Any] = {}
        for field in HOTEL_FIELDS:
            value = (
                trip_names.get(hotel.trip_id)
                if field == "trip_name"
                else getattr(hotel, field, None)
            )
            if field in ("check_in", "check_out"):
                data[field] = value.isoformat() if value else None
            elif isinstance(value, Decimal):
                data[field] = float(value)
            else:
                data[field] = value
        if include_sensitive:
            for field in HOTEL_SENSITIVE_FIELDS:
                data[field] = getattr(hotel, field, None)
        return data

    def _all_expenses(self, user_id: uuid.UUID) -> list[Expense]:
        return list(
            self.db.scalars(
                select(Expense)
                .where(Expense.user_id == user_id)
                .order_by(Expense.occurred_at.asc().nullslast(), Expense.id)
            )
        )

    def _export_expense(self, expense: Expense, trip_names: dict[uuid.UUID, str]) -> dict[str, Any]:
        data: dict[str, Any] = {}
        for field in EXPENSE_FIELDS:
            value = (
                trip_names.get(expense.trip_id)
                if field == "trip_name"
                else getattr(expense, field, None)
            )
            if field == "exchange_rate_date":
                data[field] = value.isoformat() if value else None
            elif field == "occurred_at":
                data[field] = iso_full(value)
            elif isinstance(value, Decimal):
                data[field] = float(value)
            else:
                data[field] = value
        return data

    def _all_notes(self, user_id: uuid.UUID) -> list[Note]:
        return list(
            self.db.scalars(
                select(Note).where(Note.user_id == user_id).order_by(Note.created_at.asc(), Note.id)
            )
        )

    def _export_note(self, note: Note, trip_names: dict[uuid.UUID, str]) -> dict[str, Any]:
        data: dict[str, Any] = {}
        for field in NOTE_FIELDS:
            if field == "trip_name":
                data[field] = trip_names.get(note.trip_id)
            elif field in ("created_at", "updated_at"):
                data[field] = iso_full(getattr(note, field, None))
            else:
                data[field] = getattr(note, field, None)
        return data

    def _all_places(self, user_id: uuid.UUID) -> list[Place]:
        return list(
            self.db.scalars(
                select(Place).where(Place.user_id == user_id).order_by(Place.name.asc(), Place.id)
            )
        )

    def _export_place(self, place: Place) -> dict[str, Any]:
        return {
            "id": str(place.id),
            "type": place.type,
            "country": place.country,
            "region": place.region,
            "city": place.city,
            "district": place.district,
            "name": place.name,
            "localized_name": place.localized_name,
            "lat": place.lat,
            "lon": place.lon,
            "timezone": place.timezone,
            "external_ids": place.external_ids,
        }

    def _all_activities(self, user_id: uuid.UUID) -> list[Activity]:
        return list(
            self.db.scalars(
                select(Activity)
                .where(Activity.user_id == user_id)
                .order_by(Activity.start_at.asc().nullslast(), Activity.id)
            )
        )

    def _export_activity(
        self, activity: Activity, trip_names: dict[uuid.UUID, str]
    ) -> dict[str, Any]:
        return {
            "id": str(activity.id),
            "name": activity.name,
            "type": activity.type,
            "place_id": str(activity.place_id) if activity.place_id else None,
            "trip_name": trip_names.get(activity.trip_id) if activity.trip_id else None,
            "start_at": iso_full(activity.start_at),
            "end_at": iso_full(activity.end_at),
            "price": float(activity.price) if activity.price is not None else None,
            "currency": activity.currency,
            "notes": activity.notes,
        }

    def _export_trip(self, trip: Trip) -> dict[str, Any]:
        return {
            "id": str(trip.id),
            "name": trip.name,
            "description": trip.description,
            "start_date": trip.start_date.isoformat() if trip.start_date else None,
            "end_date": trip.end_date.isoformat() if trip.end_date else None,
            "cover_image": trip.cover_image,
            "origin": trip.origin,
            "destination": trip.destination,
            "status": trip.status,
        }

    def _record_signature_row(self, record: TransportRecord) -> dict[str, Any]:
        return {
            "type": record.type,
            "service_number": record.service_number,
            "departure_time": record.departure_time,
            "origin": record.origin,
            "destination": record.destination,
        }

    def _parse(
        self, format: str, content: str
    ) -> tuple[list[str], list[dict[str, Any]], list[dict[str, Any]]]:
        if format == "json":
            return self._parse_json(content)
        return self._parse_csv(content)

    def _parse_csv(
        self, content: str
    ) -> tuple[list[str], list[dict[str, Any]], list[dict[str, Any]]]:
        text = content.lstrip("\ufeff")
        reader = csv.DictReader(io.StringIO(text))
        if reader.fieldnames is None:
            return [], [], []
        columns = [c.strip() for c in reader.fieldnames if c is not None]
        rows = [
            {
                str(k).strip(): (v.strip() if isinstance(v, str) else v)
                for k, v in row.items()
                if k is not None
            }
            for row in reader
        ]
        return columns, rows, []

    def _parse_json(
        self, content: str
    ) -> tuple[list[str], list[dict[str, Any]], list[dict[str, Any]]]:
        try:
            data = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON: {exc}") from None
        trips: list[dict[str, Any]] = []
        if isinstance(data, dict):
            if "records" not in data:
                raise ValueError("JSON must contain a 'records' array")
            records = data["records"]
            trips = data.get("trips") or []
        elif isinstance(data, list):
            records = data
        else:
            raise ValueError("JSON must be an object with 'records' or an array")
        if not isinstance(records, list):
            raise ValueError("'records' must be an array")
        columns = sorted({k for row in records if isinstance(row, dict) for k in row})
        return (
            columns,
            [r for r in records if isinstance(r, dict)],
            [t for t in trips if isinstance(t, dict)],
        )

    def _resolve_mapping(
        self, columns: list[str], overrides: dict[str, str] | None
    ) -> dict[str, str]:
        mapping: dict[str, str] = {}
        for column in columns:
            canonical = _norm_header(column)
            # Explicit overrides always win, including for canonical headers and
            # empty strings (which intentionally ignore the column).
            if overrides and column in overrides:
                mapping[column] = overrides[column]
            elif overrides and canonical in overrides:
                mapping[column] = overrides[canonical]
            elif canonical in RECORD_FIELDS or canonical in SENSITIVE_FIELDS:
                mapping[column] = canonical
            else:
                mapping[column] = FIELD_ALIASES.get(canonical, "")
        return mapping

    def _normalize_row(
        self, raw: dict[str, Any], mapping: dict[str, str]
    ) -> tuple[dict[str, Any], list[tuple[str | None, str]]]:
        normalized: dict[str, Any] = {"status": "scheduled", "type": "flight"}
        errors: list[tuple[str | None, str]] = []

        # Resolve timezone columns first so naive datetimes in the same row can be
        # localized correctly, regardless of column order.
        row_tz: dict[str, str] = {}
        for source, field in mapping.items():
            if field not in ("departure_timezone", "arrival_timezone"):
                continue
            value = raw.get(source)
            if isinstance(value, str) and value.strip():
                row_tz[field] = value.strip()
                normalized[field] = value.strip()

        for source, field in mapping.items():
            if not field or field not in RECORD_FIELDS and field not in SENSITIVE_FIELDS:
                continue
            if field in ("departure_timezone", "arrival_timezone"):
                continue
            value = raw.get(source)
            if field == "trip_name":
                normalized["trip_name"] = value.strip() if isinstance(value, str) else value
                continue
            if field in DATETIME_FIELDS:
                tz_field = (
                    "arrival_timezone"
                    if field.startswith(("arrival", "actual_arrival"))
                    else "departure_timezone"
                )
                try:
                    parsed = parse_datetime(value, row_tz.get(tz_field))
                    if parsed is not None:
                        normalized[field] = parsed
                except ValueError:
                    errors.append((field, "unrecognized datetime"))
                continue
            if field in DECIMAL_FIELDS:
                if value not in (None, ""):
                    try:
                        normalized[field] = Decimal(str(value).replace(",", ""))
                    except InvalidOperation:
                        errors.append((field, "invalid number"))
                continue
            if field == "type":
                normalized["type"] = normalize_type(value)
                continue
            if field == "status":
                # Normalize through the canonical vocabulary (aliases included) so
                # imports cannot smuggle free-form statuses past the tightened
                # create schemas; unknown values fall back to the default.
                normalized["status"] = normalize_record_status(value)
                continue
            if isinstance(value, str):
                value = value.strip() or None
            if value is not None:
                normalized[field] = value
        # validate against the per-type create schema (required origin/destination, lengths)
        record_type = normalized.get("type", "flight")
        create_model = CREATE_BY_TYPE.get(record_type, FlightCreate)
        try:
            create_model.model_validate(normalized)
        except ValidationError as exc:
            for error in exc.errors():
                errors.append(
                    (
                        error.get("loc", ("",))[0] if error.get("loc") else None,
                        error.get("msg", "invalid value"),
                    )
                )
        return normalized, errors

    def _create_record(
        self, user_id: uuid.UUID, normalized: dict[str, Any], trip_ids: dict[str, uuid.UUID]
    ) -> None:
        record_type = normalized.get("type", "flight")
        create_model = CREATE_BY_TYPE.get(record_type, FlightCreate)
        service_cls = SERVICE_BY_TYPE.get(record_type, FlightService)
        trip_name = normalized.pop("trip_name", None)
        payload = create_model.model_validate(normalized)
        if trip_name:
            trip_id = trip_ids.get(trip_name)
            payload = payload.model_copy(update={"trip_id": trip_id if trip_id else None})
        service = service_cls(self.db)
        # The import loop already skipped duplicates via `existing`; bypass the
        # service-level check to avoid a second (and uncaught) conflict.
        service.create_record(user_id=user_id, payload=payload, force=True)

    def _ensure_trips(
        self, user_id: uuid.UUID, trips: list[dict[str, Any]]
    ) -> tuple[dict[str, uuid.UUID], int]:
        existing = {trip.name: trip.id for trip in self._all_trips(user_id)}
        created = 0
        for trip in trips:
            name = (trip.get("name") or "").strip()
            if not name or name in existing:
                continue
            data = {field: trip.get(field) for field in TRIP_FIELDS if field in trip}
            if "status" in data:
                # Trip rows bypass the Pydantic schemas (direct model insert),
                # so normalize here to keep the vocabulary closed.
                data["status"] = normalize_trip_status(data["status"])
            for field in ("start_date", "end_date"):
                if data.get(field):
                    try:
                        data[field] = parse_date(data[field])
                    except ValueError:
                        data[field] = None
            new_trip = Trip(
                user_id=user_id, name=name, **{k: v for k, v in data.items() if k != "name"}
            )
            self.db.add(new_trip)
            self.db.flush()
            existing[name] = new_trip.id
            created += 1
        self.db.commit()
        return existing, created

    def _json_safe(self, data: dict[str, Any]) -> dict[str, Any]:
        safe: dict[str, Any] = {}
        for key, value in data.items():
            if isinstance(value, datetime):
                safe[key] = iso_full(value)
            elif isinstance(value, Decimal):
                safe[key] = float(value)
            elif value is None:
                safe[key] = None
            else:
                safe[key] = value
        return safe
