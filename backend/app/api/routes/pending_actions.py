"""Approval inbox for agent-proposed writes (spec #69, #85).

Every route here requires a browser session: ``get_current_session_user``
rejects personal access tokens, so an agent cannot approve its own proposal
even if a prompt tells it to.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.api.deps import (
    get_audit_service,
    get_current_session_user,
    get_pending_action_service,
)
from app.models.audit_log import AuditAction
from app.models.pending_action import PendingActionStatus
from app.models.user import User
from app.schemas.pending_action import (
    PendingActionConfirm,
    PendingActionList,
    PendingActionRead,
)
from app.services.audit import AuditService
from app.services.pending_action import (
    PendingActionInvalidError,
    PendingActionNotFoundError,
    PendingActionService,
    PendingActionStateError,
)
from app.services.transport import DuplicateRecordError

router = APIRouter(prefix="/pending-actions", tags=["pending-actions"])


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pending action not found")


def _state_error(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


@router.get("", response_model=PendingActionList)
def list_pending_actions(
    status_filter: str | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_session_user),
    service: PendingActionService = Depends(get_pending_action_service),
) -> PendingActionList:
    if status_filter is not None and status_filter not in PendingActionStatus.ALL:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown status: {status_filter}",
        )
    items, total, pending_total = service.list_for_user(
        user_id=current_user.id, status=status_filter, page=page, page_size=page_size
    )
    return PendingActionList(
        items=items, total=total, page=page, page_size=page_size, pending_total=pending_total
    )


@router.get("/{action_id}", response_model=PendingActionRead)
def get_pending_action(
    action_id: uuid.UUID,
    current_user: User = Depends(get_current_session_user),
    service: PendingActionService = Depends(get_pending_action_service),
) -> PendingActionRead:
    try:
        return service.get(user_id=current_user.id, action_id=action_id)
    except PendingActionNotFoundError:
        raise _not_found() from None


@router.post("/{action_id}/confirm", response_model=PendingActionRead)
def confirm_pending_action(
    action_id: uuid.UUID,
    payload: PendingActionConfirm,
    request: Request,
    current_user: User = Depends(get_current_session_user),
    service: PendingActionService = Depends(get_pending_action_service),
    audit: AuditService = Depends(get_audit_service),
) -> PendingActionRead:
    try:
        record, written = service.confirm(
            user_id=current_user.id, action_id=action_id, force=payload.force
        )
    except PendingActionNotFoundError:
        raise _not_found() from None
    except PendingActionStateError as exc:
        raise _state_error(f"Pending action is already {exc}") from None
    except DuplicateRecordError as exc:
        existing = exc.existing_record
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "Duplicate record",
                "existing_record": {
                    "id": str(existing.id),
                    "service_number": existing.service_number,
                    "carrier": existing.carrier,
                    "departure_time": (
                        existing.departure_time.isoformat() if existing.departure_time else None
                    ),
                    "origin": existing.origin,
                    "destination": existing.destination,
                },
            },
        ) from None
    except PendingActionInvalidError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc) or "Proposal failed"
        ) from None

    audit.log(
        action=AuditAction.CONFIRM_PENDING_ACTION,
        user_id=current_user.id,
        resource_type="pending_action",
        resource_id=str(record.id),
        meta={
            "action": record.action,
            "record_type": record.record_type,
            "token_name": record.token_name,
            "record_id": str(written.id),
            "force": payload.force,
        },
        request=request,
    )
    return record


@router.post("/{action_id}/reject", response_model=PendingActionRead)
def reject_pending_action(
    action_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_session_user),
    service: PendingActionService = Depends(get_pending_action_service),
    audit: AuditService = Depends(get_audit_service),
) -> PendingActionRead:
    try:
        record = service.reject(user_id=current_user.id, action_id=action_id)
    except PendingActionNotFoundError:
        raise _not_found() from None
    except PendingActionStateError as exc:
        raise _state_error(f"Pending action is already {exc}") from None

    audit.log(
        action=AuditAction.REJECT_PENDING_ACTION,
        user_id=current_user.id,
        resource_type="pending_action",
        resource_id=str(record.id),
        meta={
            "action": record.action,
            "record_type": record.record_type,
            "token_name": record.token_name,
        },
        request=request,
    )
    return record
