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
from app.schemas.transport import (
    FlightCreate,
    FlightUpdate,
    OtherTransportCreate,
    OtherTransportUpdate,
    TrainCreate,
    TrainUpdate,
)
from app.services.transport import (
    DuplicateRecordError,
    FlightService,
    OtherTransportService,
    RecordNotFoundError,
    TrainService,
)

#: How long an agent's proposal stays actionable. Agents can be slow, humans
#: slower, but an unbounded queue of stale writes is a liability.
DEFAULT_TTL = timedelta(days=7)

RECORD_TYPES = ("flight", "train", "other")

_CREATE_SCHEMAS = {
    "flight": FlightCreate,
    "train": TrainCreate,
    "other": OtherTransportCreate,
}

_UPDATE_SCHEMAS = {
    "flight": FlightUpdate,
    "train": TrainUpdate,
    "other": OtherTransportUpdate,
}

_SERVICES = {
    "flight": FlightService,
    "train": TrainService,
    "other": OtherTransportService,
}


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
    label = {"flight": "Flight", "train": "Train", "other": "Transport"}.get(
        record_type, record_type
    )
    if action == PendingActionKind.CREATE:
        route = f"{payload.get('origin') or '—'} → {payload.get('destination') or '—'}"
        parts = [f"Create {label}", route]
        if payload.get("service_number"):
            parts.append(str(payload["service_number"]))
        if payload.get("departure_time"):
            parts.append(str(payload["departure_time"]))
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

    def reject(self, *, user_id: uuid.UUID, action_id: uuid.UUID) -> PendingAction:
        record = self.get(user_id=user_id, action_id=action_id)
        if record.status != PendingActionStatus.PENDING:
            raise PendingActionStateError(record.status)
        record.status = PendingActionStatus.REJECTED
        record.resolved_at = utcnow()
        self.db.commit()
        self.db.refresh(record)
        return record

    def confirm(
        self, *, user_id: uuid.UUID, action_id: uuid.UUID, force: bool = False
    ) -> tuple[PendingAction, Any]:
        """Execute a proposal and return the written record.

        ``DuplicateRecordError`` deliberately propagates while the action stays
        pending: the user can look at the existing record and retry with
        ``force=True``, exactly like the duplicate flow in the web UI (#41).
        """
        record = self.get(user_id=user_id, action_id=action_id)
        if record.status != PendingActionStatus.PENDING:
            raise PendingActionStateError(record.status)

        service = _SERVICES[record.record_type](self.db)
        payload = record.payload or {}
        try:
            if record.action == PendingActionKind.CREATE:
                schema = _CREATE_SCHEMAS[record.record_type]
                written = service.create_record(
                    user_id=user_id, payload=schema.model_validate(payload), force=force
                )
            elif record.action == PendingActionKind.UPDATE:
                schema = _UPDATE_SCHEMAS[record.record_type]
                written = service.update_record(
                    user_id=user_id,
                    record_id=uuid.UUID(payload["record_id"]),
                    payload=schema.model_validate(payload.get("data") or {}),
                )
            else:  # pragma: no cover - guarded at creation
                raise PendingActionInvalidError(record.action)
        except DuplicateRecordError:
            raise
        except (RecordNotFoundError, PendingActionInvalidError, ValueError, KeyError) as exc:
            record.status = PendingActionStatus.FAILED
            record.error = str(exc)[:500]
            record.resolved_at = utcnow()
            self.db.commit()
            self.db.refresh(record)
            raise PendingActionInvalidError(str(exc)) from None

        record.status = PendingActionStatus.CONFIRMED
        record.result = {"record_type": record.record_type, "record_id": str(written.id)}
        record.resolved_at = utcnow()
        self.db.commit()
        self.db.refresh(record)
        return record, written
