"""Import / export of user-owned records (spec #42/#43)."""

from __future__ import annotations

import csv
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

from app.models.transport_record import TransportRecord
from app.models.trip import Trip
from app.models.user import User
from app.schemas.data_transfer import (
    ImportDuplicate,
    ImportPreview,
    ImportResult,
    ImportRowError,
)
from app.schemas.transport import FlightCreate, OtherTransportCreate, TrainCreate
from app.services.dedup import iso_full, record_signature, record_signature_from_model
from app.services.transport import FlightService, OtherTransportService, TrainService

EXPORT_VERSION = 1
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

    def export_json(self, *, user_id: uuid.UUID, include_sensitive: bool = False) -> str:
        records = self._all_records(user_id)
        trip_names = {trip.id: trip.name for trip in self._all_trips(user_id)}
        user = self.db.get(User, user_id)
        bundle = {
            "version": EXPORT_VERSION,
            "exported_at": datetime.now(UTC).isoformat(),
            "include_sensitive": include_sensitive,
            "settings": {
                "display_name": user.display_name if user else None,
                "email": user.email if user else None,
                "locale": user.locale if user else None,
                "timezone": user.timezone if user else None,
                "currency": user.currency if user else None,
            },
            "trips": [self._export_trip(t) for t in self._all_trips(user_id)],
            "records": [self._export_record(r, include_sensitive, trip_names) for r in records],
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
            {"version": EXPORT_VERSION, "trips": [], "records": [sample]},
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
        )

    def import_records(
        self,
        *,
        user_id: uuid.UUID,
        format: str,
        content: str,
        mapping: dict[str, str] | None = None,
    ) -> ImportResult:
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

    # ---------------- helpers ----------------
    def _all_records(self, user_id: uuid.UUID) -> list[TransportRecord]:
        return list(
            self.db.scalars(select(TransportRecord).where(TransportRecord.user_id == user_id))
        )

    def _all_trips(self, user_id: uuid.UUID) -> list[Trip]:
        return list(self.db.scalars(select(Trip).where(Trip.user_id == user_id)))

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
                normalized["status"] = str(value or "scheduled").strip().lower() or "scheduled"
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
