"""Pending actions: agent writes that wait for a human (spec #69, #85).

MCP write tools do not touch business data. They validate the arguments, store a
``PendingAction`` and return its id; the record is created only when the owner
approves the proposal from a browser session. That indirection is the point: an
agent (or a prompt injected into it) can never approve its own request.
"""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Any

from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.pending_action import PendingAction, PendingActionKind, PendingActionStatus
from app.models.user import utcnow
from app.schemas.activity import ActivityCreate, ActivityUpdate
from app.schemas.expense import ExpenseCreate, ExpenseUpdate
from app.schemas.hotel import HotelCreate, HotelUpdate
from app.schemas.note import NoteCreate, NoteUpdate
from app.schemas.place import PlaceCreate, PlaceUpdate
from app.schemas.transport import (
    FlightCreate,
    FlightUpdate,
    OtherTransportCreate,
    OtherTransportUpdate,
    TrainCreate,
    TrainUpdate,
)
from app.schemas.trip import TripCreate, TripUpdate
from app.services.activity import ActivityNotFoundError, ActivityService, InvalidActivityWindowError
from app.services.expense import ExpenseNotFoundError, ExpenseService
from app.services.hotel import DuplicateHotelError, HotelService
from app.services.note import NoteNotFoundError, NoteService
from app.services.place import PlaceNotFoundError, PlaceService
from app.services.transport import (
    DuplicateRecordError,
    FlightService,
    OtherTransportService,
    RecordNotFoundError,
    TrainService,
)
from app.services.trip import TripNotFoundError, TripService
from app.services.write_lock import lock_user_writes

#: How long an agent's proposal stays actionable. Agents can be slow, humans
#: slower, but an unbounded queue of stale writes is a liability.
DEFAULT_TTL = timedelta(days=7)

RECORD_TYPES = (
    "flight",
    "train",
    "other",
    "hotel",
    "trip",
    "expense",
    "note",
    "place",
    "activity",
)

_CREATE_SCHEMAS = {
    "flight": FlightCreate,
    "train": TrainCreate,
    "other": OtherTransportCreate,
    "hotel": HotelCreate,
    "trip": TripCreate,
    "expense": ExpenseCreate,
    "note": NoteCreate,
    "place": PlaceCreate,
    "activity": ActivityCreate,
}

_UPDATE_SCHEMAS = {
    "flight": FlightUpdate,
    "train": TrainUpdate,
    "other": OtherTransportUpdate,
    "hotel": HotelUpdate,
    "trip": TripUpdate,
    "expense": ExpenseUpdate,
    "note": NoteUpdate,
    "place": PlaceUpdate,
    "activity": ActivityUpdate,
}

_SERVICES = {
    "flight": FlightService,
    "train": TrainService,
    "other": OtherTransportService,
    "hotel": HotelService,
    "trip": TripService,
    "expense": ExpenseService,
    "note": NoteService,
    "place": PlaceService,
    "activity": ActivityService,
}

#: record types whose services expose a uniform ``create_record`` / ``update_record``
#: with duplicate detection (``force``). The other entities have no duplicate
#: concept, so they are called via their ``create_<type>`` / ``update_<type>``
#: and ignore ``force``.
_DUPLICATE_TYPES = frozenset({"flight", "train", "other", "hotel"})

#: Human-readable labels for proposal summaries / the approval inbox.
_LABELS = {
    "flight": "Flight",
    "train": "Train",
    "other": "Transport",
    "hotel": "Hotel",
    "trip": "Trip",
    "expense": "Expense",
    "note": "Note",
    "place": "Place",
    "activity": "Activity",
}


def _service_create(record_type: str, service, *, user_id, payload, force: bool):
    """Dispatch a confirmed create to the entity's own service method."""
    if record_type in _DUPLICATE_TYPES:
        return service.create_record(user_id=user_id, payload=payload, force=force, commit=False)
    return getattr(service, f"create_{record_type}")(user_id=user_id, payload=payload, commit=False)


def _service_update(record_type: str, service, *, user_id, record_id, payload):
    """Dispatch a confirmed update; the id kwarg name varies per entity."""
    if record_type in _DUPLICATE_TYPES:
        return service.update_record(
            user_id=user_id, record_id=record_id, payload=payload, commit=False
        )
    if record_type == "trip":
        return service.update_trip(
            user_id=user_id, trip_id=record_id, payload=payload, commit=False
        )
    return getattr(service, f"update_{record_type}")(
        user_id=user_id, **{f"{record_type}_id": record_id}, payload=payload, commit=False
    )


class PendingActionNotFoundError(Exception):
    """Unknown id, or a proposal owned by another user (spec #57)."""


class PendingActionStateError(Exception):
    """The proposal already has a decision and cannot be acted on again."""


class PendingActionInvalidError(Exception):
    """The stored payload no longer validates (schema drift)."""


class InvalidProposalError(Exception):
    """Arguments sent by an agent did not validate; shown back to the agent."""

    def __init__(self, errors: list[dict[str, Any]]) -> None:
        self.errors = errors
        super().__init__("Invalid proposal")


def _validation_errors(exc: ValidationError) -> list[dict[str, Any]]:
    return [
        {
            "field": ".".join(str(part) for part in err["loc"]),
            "message": err["msg"],
        }
        for err in exc.errors()
    ]


def validate_create(record_type: str, data: dict[str, Any]) -> dict[str, Any]:
    """Validate a proposed create and return a JSON-safe payload.

    Doing this before the proposal is shown means the user never approves
    something the API would reject later, and the agent gets a precise error
    while it can still fix its call.
    """
    schema = _CREATE_SCHEMAS.get(record_type)
    if schema is None:
        raise InvalidProposalError(
            [{"field": "record_type", "message": f"must be one of {', '.join(RECORD_TYPES)}"}]
        )
    if not isinstance(data, dict):
        raise InvalidProposalError([{"field": "data", "message": "must be an object"}])
    try:
        return schema.model_validate(data).model_dump(mode="json")
    except ValidationError as exc:
        raise InvalidProposalError(_validation_errors(exc)) from None


def validate_update(record_type: str, record_id: str, data: dict[str, Any]) -> dict[str, Any]:
    """Validate a proposed update; ``record_id`` is checked at confirm time."""
    schema = _UPDATE_SCHEMAS.get(record_type)
    if schema is None:
        raise InvalidProposalError(
            [{"field": "record_type", "message": f"must be one of {', '.join(RECORD_TYPES)}"}]
        )
    if not isinstance(data, dict) or not data:
        raise InvalidProposalError([{"field": "data", "message": "must be a non-empty object"}])
    try:
        parsed_id = uuid.UUID(str(record_id))
    except (TypeError, ValueError):
        raise InvalidProposalError([{"field": "record_id", "message": "must be a UUID"}]) from None
    try:
        patch = schema.model_validate(data).model_dump(mode="json", exclude_unset=True)
    except ValidationError as exc:
        raise InvalidProposalError(_validation_errors(exc)) from None
    if not patch:
        raise InvalidProposalError([{"field": "data", "message": "no fields to update"}])
    return {"record_id": str(parsed_id), "data": patch}


def describe(action: str, record_type: str, payload: dict[str, Any]) -> str:
    """One-line summary for the approval inbox and the agent's tool result."""
    label = _LABELS.get(record_type, record_type)
    if action == PendingActionKind.CREATE:
        if record_type == "hotel":
            parts = [f"Create {label}", payload.get("hotel") or "—"]
            if payload.get("check_in"):
                parts.append(str(payload["check_in"]))
            if payload.get("check_out"):
                parts.append(f"→ {payload['check_out']}")
            return " · ".join(parts)

        if record_type in ("flight", "train", "other"):
            route = f"{payload.get('origin') or '—'} → {payload.get('destination') or '—'}"
            parts = [f"Create {label}", route]
            if payload.get("service_number"):
                parts.append(str(payload["service_number"]))
            if payload.get("departure_time"):
                parts.append(str(payload["departure_time"]))
            return " · ".join(parts)

        parts = [f"Create {label}"]
        if record_type == "trip":
            parts.append(payload.get("name") or "—")
            if payload.get("start_date"):
                parts.append(str(payload["start_date"]))
        elif record_type == "expense":
            if payload.get("category"):
                parts.append(str(payload["category"]))
            amount = payload.get("amount")
            if amount is not None:
                parts.append(f"{amount} {payload.get('currency') or ''}".strip())
            if payload.get("description"):
                parts.append(str(payload["description"]))
        elif record_type == "place":
            parts.append(payload.get("name") or "—")
            if payload.get("type"):
                parts.append(str(payload["type"]))
        elif record_type == "activity":
            parts.append(payload.get("name") or "—")
            if payload.get("type"):
                parts.append(str(payload["type"]))
            if payload.get("start_at"):
                parts.append(str(payload["start_at"]))
        elif record_type == "note":
            parts.append(payload.get("title") or "—")
        return " · ".join(parts)

    data = payload.get("data") or {}
    changed = ", ".join(sorted(data))
    return f"Update {label} {payload.get('record_id', '')} · {changed}"


def _as_utc(value):
    """SQLite hands back naive datetimes for timezone-aware columns."""
    from datetime import UTC

    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class PendingActionService:
    def __init__(self, db: Session) -> None:
        self.db = db

    # -- creation ---------------------------------------------------------

    def create(
        self,
        *,
        user_id: uuid.UUID,
        action: str,
        record_type: str,
        payload: dict[str, Any],
        summary: str | None = None,
        token_id: uuid.UUID | None = None,
        token_name: str | None = None,
        ttl: timedelta | None = DEFAULT_TTL,
    ) -> PendingAction:
        if action not in PendingActionKind.ALL:
            raise ValueError(f"Unknown action: {action}")
        if record_type not in RECORD_TYPES:
            raise ValueError(f"Unknown record type: {record_type}")

        record = PendingAction(
            user_id=user_id,
            token_id=token_id,
            token_name=token_name,
            action=action,
            record_type=record_type,
            summary=summary or describe(action, record_type, payload),
            payload=payload,
            status=PendingActionStatus.PENDING,
            expires_at=utcnow() + ttl if ttl is not None else None,
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    # -- reads ------------------------------------------------------------

    def _expire_if_stale(self, record: PendingAction) -> PendingAction:
        if (
            record.status == PendingActionStatus.PENDING
            and record.expires_at is not None
            and _as_utc(record.expires_at) <= utcnow()
        ):
            record.status = PendingActionStatus.EXPIRED
            record.resolved_at = utcnow()
            self.db.commit()
            self.db.refresh(record)
        return record

    def get(self, *, user_id: uuid.UUID, action_id: uuid.UUID) -> PendingAction:
        record = self.db.scalar(
            select(PendingAction).where(
                PendingAction.id == action_id,
                PendingAction.user_id == user_id,
            )
        )
        if record is None:
            raise PendingActionNotFoundError(str(action_id))
        return self._expire_if_stale(record)

    def list_for_user(
        self,
        *,
        user_id: uuid.UUID,
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[PendingAction], int, int]:
        stmt = select(PendingAction).where(PendingAction.user_id == user_id)
        if status:
            stmt = stmt.where(PendingAction.status == status)

        total = self.db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        pending_total = (
            self.db.scalar(
                select(func.count())
                .select_from(PendingAction)
                .where(
                    PendingAction.user_id == user_id,
                    PendingAction.status == PendingActionStatus.PENDING,
                )
            )
            or 0
        )
        items = list(
            self.db.scalars(
                stmt.order_by(PendingAction.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        return items, total, pending_total

    # -- decisions --------------------------------------------------------

    def reject(
        self, *, user_id: uuid.UUID, action_id: uuid.UUID, commit: bool = True
    ) -> PendingAction:
        lock_user_writes(self.db, user_id)
        record = self.get(user_id=user_id, action_id=action_id)
        if record.status != PendingActionStatus.PENDING:
            raise PendingActionStateError(record.status)
        record.status = PendingActionStatus.REJECTED
        record.resolved_at = utcnow()
        if commit:
            self.db.commit()
        else:
            self.db.flush()
        self.db.refresh(record)
        return record

    def confirm(
        self, *, user_id: uuid.UUID, action_id: uuid.UUID, force: bool = False, commit: bool = True
    ) -> tuple[PendingAction, Any]:
        """Execute a proposal and return the written record.

        ``DuplicateRecordError`` deliberately propagates while the action stays
        pending: the user can look at the existing record and retry with
        ``force=True``, exactly like the duplicate flow in the web UI (#41).
        """
        lock_user_writes(self.db, user_id)
        record = self.get(user_id=user_id, action_id=action_id)
        if record.status != PendingActionStatus.PENDING:
            raise PendingActionStateError(record.status)

        service = _SERVICES[record.record_type](self.db)
        payload = record.payload or {}
        try:
            if record.action == PendingActionKind.CREATE:
                schema = _CREATE_SCHEMAS[record.record_type]
                if record.record_type == "activity":
                    # A retried confirmation must not create a second event.
                    written, _ = service.create_activity_idempotent(
                        user_id=user_id,
                        payload=schema.model_validate(payload),
                        idempotency_key=f"pending:{record.id}",
                        idempotency_operation="confirm_pending_action",
                        commit=False,
                    )
                elif record.record_type == "expense":
                    # Same guarantee for a spend approved from the AI inbox.
                    written, _ = service.create_expense_idempotent(
                        user_id=user_id,
                        payload=schema.model_validate(payload),
                        idempotency_key=f"pending:{record.id}",
                        idempotency_operation="confirm_pending_action",
                        commit=False,
                    )
                else:
                    written = _service_create(
                        record.record_type,
                        service,
                        user_id=user_id,
                        payload=schema.model_validate(payload),
                        force=force,
                    )
            elif record.action == PendingActionKind.UPDATE:
                schema = _UPDATE_SCHEMAS[record.record_type]
                written = _service_update(
                    record.record_type,
                    service,
                    user_id=user_id,
                    record_id=uuid.UUID(payload["record_id"]),
                    payload=schema.model_validate(payload.get("data") or {}),
                )
            else:  # pragma: no cover - guarded at creation
                raise PendingActionInvalidError(record.action)
        except (DuplicateRecordError, DuplicateHotelError):
            self.db.rollback()
            raise
        except (
            RecordNotFoundError,
            TripNotFoundError,
            ExpenseNotFoundError,
            NoteNotFoundError,
            PlaceNotFoundError,
            ActivityNotFoundError,
            InvalidActivityWindowError,
            PendingActionInvalidError,
            ValueError,
            KeyError,
        ) as exc:
            # The operation may already have flushed a reservation or changed
            # other rows. Never commit those writes with the failure status.
            self.db.rollback()
            lock_user_writes(self.db, user_id)
            record = self.get(user_id=user_id, action_id=action_id)
            if record.status != PendingActionStatus.PENDING:
                raise PendingActionStateError(record.status) from None
            record.status = PendingActionStatus.FAILED
            record.error = str(exc)[:500]
            record.resolved_at = utcnow()
            self.db.commit()
            self.db.refresh(record)
            raise PendingActionInvalidError(str(exc)) from None

        record.status = PendingActionStatus.CONFIRMED
        record.result = {"record_type": record.record_type, "record_id": str(written.id)}
        record.resolved_at = utcnow()
        if commit:
            self.db.commit()
        else:
            self.db.flush()
        self.db.refresh(record)
        return record, written
