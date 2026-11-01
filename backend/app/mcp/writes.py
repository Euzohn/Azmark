"""MCP write tools — they only *propose*, never write (spec #69, #85).

A model drives the MCP client, so a tool call is not the user's consent. These
handlers validate the arguments, store a ``PendingAction`` and tell the agent to
ask the owner to approve it in the Azmark web UI. Deletion is deliberately not
exposed: destructive tools stay in-app where confirmation is guaranteed.
"""

from __future__ import annotations

from typing import Any

from mcp.types import Tool
from sqlalchemy.orm import Session

from app.mcp.auth import MCPIdentity
from app.models.pending_action import PendingActionKind
from app.services.pending_action import (
    InvalidProposalError,
    PendingActionService,
    describe,
    validate_create,
    validate_update,
)

_RECORD_TYPE = {
    "type": "string",
    "enum": ["flight", "train", "other", "hotel"],
    "description": "Which record type this proposal targets (hotel = accommodation)",
}

WRITE_TOOL_DEFINITIONS: list[Tool] = [
    Tool(
        name="create_record",
        description=(
            "Propose creating a transport record. Nothing is saved: the call "
            "returns a pending_action_id and the owner must approve it in the "
            "Azmark web UI (Pending actions). Use get_pending_action to check "
            "whether it was confirmed."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "record_type": _RECORD_TYPE,
                "data": {
                    "type": "object",
                    "description": (
                        "Record fields. For transport (flight/train/other): "
                        "origin, destination, departure_time, arrival_time, "
                        "carrier, service_number, seat, notes, trip_id. For "
                        "hotel: hotel, check_in, check_out, room_type, "
                        "room_number, booking_reference, price, currency, "
                        "address, notes, trip_id. Same shape as POST "
                        "/api/v1/<type>."
                    ),
                },
            },
            "required": ["record_type", "data"],
        },
    ),
    Tool(
        name="update_record",
        description=(
            "Propose changing fields on an existing record. Nothing is saved: "
            "the owner must approve the proposal in the Azmark web UI."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "record_type": _RECORD_TYPE,
                "record_id": {"type": "string", "description": "UUID of the record to update"},
                "data": {
                    "type": "object",
                    "description": "Only the fields to change (partial update).",
                },
            },
            "required": ["record_type", "record_id", "data"],
        },
    ),
]

WRITE_TOOL_NAMES = frozenset(tool.name for tool in WRITE_TOOL_DEFINITIONS)

#: Readable with any token: an agent may always ask what happened to a proposal
#: it already created, and the status leaks nothing new.
STATUS_TOOL_DEFINITIONS: list[Tool] = [
    Tool(
        name="get_pending_action",
        description=(
            "Check a proposal created by create_record/update_record. Returns "
            "status: pending, confirmed, rejected, failed or expired."
        ),
        inputSchema={
            "type": "object",
            "properties": {"pending_action_id": {"type": "string"}},
            "required": ["pending_action_id"],
        },
    ),
]

STATUS_TOOL_NAMES = frozenset(tool.name for tool in STATUS_TOOL_DEFINITIONS)


def _pending_payload(record) -> dict[str, Any]:
    return {
        "status": "pending_confirmation",
        "pending_action_id": str(record.id),
        "summary": record.summary,
        "expires_at": record.expires_at.isoformat() if record.expires_at else None,
        "message": (
            "Nothing was saved. Ask the owner to approve this proposal in "
            "Azmark -> Pending actions, then call get_pending_action with this id."
        ),
    }


def _status_payload(record) -> dict[str, Any]:
    return {
        "pending_action_id": str(record.id),
        "status": record.status,
        "summary": record.summary,
        "result": record.result,
        "error": record.error,
        "resolved_at": record.resolved_at.isoformat() if record.resolved_at else None,
    }


def handle_write(
    *, db: Session, identity: MCPIdentity, name: str, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Validate a write proposal and persist it for human approval."""
    record_type = arguments.get("record_type")
    data = arguments.get("data")

    service = PendingActionService(db)
    try:
        if name == "create_record":
            payload = validate_create(str(record_type), data)
            action = PendingActionKind.CREATE
        elif name == "update_record":
            payload = validate_update(str(record_type), arguments.get("record_id"), data)
            action = PendingActionKind.UPDATE
        else:  # pragma: no cover - names come from WRITE_TOOL_NAMES
            return {"error": f"unknown write tool: {name}"}
    except InvalidProposalError as exc:
        return {"error": "invalid proposal", "fields": exc.errors}

    record = service.create(
        user_id=identity.user_id,
        action=action,
        record_type=str(record_type),
        payload=payload,
        summary=describe(action, str(record_type), payload),
        token_id=identity.token_id,
        token_name=identity.token_name,
    )
    _audit_create(db, identity=identity, record=record)
    return _pending_payload(record)


def _audit_create(db: Session, *, identity: MCPIdentity, record) -> None:
    """Record who proposed what. MCP has no HTTP request, so no IP hash."""
    from app.models.audit_log import AuditAction
    from app.services.audit import AuditService

    AuditService(db).log(
        action=AuditAction.CREATE_PENDING_ACTION,
        user_id=identity.user_id,
        resource_type="pending_action",
        resource_id=str(record.id),
        meta={
            "action": record.action,
            "record_type": record.record_type,
            "actor": {
                "kind": "access_token",
                "id": str(identity.token_id),
                "name": identity.token_name,
            },
        },
    )


def handle_status(
    *, db: Session, identity: MCPIdentity, name: str, arguments: dict[str, Any]
) -> dict[str, Any]:
    import uuid

    from app.services.pending_action import PendingActionNotFoundError

    try:
        action_id = uuid.UUID(str(arguments.get("pending_action_id")))
    except (TypeError, ValueError):
        return {"error": "pending_action_id must be a UUID"}

    try:
        record = PendingActionService(db).get(user_id=identity.user_id, action_id=action_id)
    except PendingActionNotFoundError:
        # Same answer for "does not exist" and "belongs to someone else" (#57).
        return {"error": "pending action not found"}
    return _status_payload(record)
