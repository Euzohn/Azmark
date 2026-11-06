import uuid
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status

from app.api.deps import get_audit_service, get_current_user, get_expense_service
from app.models.audit_log import AuditAction
from app.models.user import User
from app.schemas.expense import (
    ExpenseCategory,
    ExpenseCreate,
    ExpenseList,
    ExpenseRead,
    ExpenseSourceType,
    ExpenseUpdate,
)
from app.services.audit import AuditService
from app.services.expense import (
    ExpenseNotFoundError,
    ExpenseService,
    ExpenseSourceNotFoundError,
    ExpenseSourceTypeError,
    ExpenseTripAssignmentError,
    ExpenseTripConflictError,
    InvalidExpenseAmountsError,
)
from app.services.idempotency import (
    IdempotencyConflictError,
    IdempotencyInProgressError,
    IdempotencyResultGoneError,
)

router = APIRouter(prefix="/expenses", tags=["expenses"])

ExpenseSort = Literal["newest", "oldest", "amount", "created"]


@router.get("", response_model=ExpenseList)
def list_expenses(
    search: str | None = None,
    category: ExpenseCategory | None = None,
    trip_id: uuid.UUID | None = None,
    source_type: ExpenseSourceType | None = None,
    source_id: uuid.UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    sort: ExpenseSort = "newest",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    service: ExpenseService = Depends(get_expense_service),
) -> ExpenseList:
    items, total = service.list_expenses(
        user_id=current_user.id,
        search=search,
        category=category,
        trip_id=trip_id,
        source_type=source_type,
        source_id=source_id,
        date_from=date_from,
        date_to=date_to,
        sort=sort,
        page=page,
        page_size=page_size,
    )
    return ExpenseList(items=items, total=total, page=page, page_size=page_size)


@router.post("", response_model=ExpenseRead, status_code=status.HTTP_201_CREATED)
def create_expense(
    payload: ExpenseCreate,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", max_length=120),
    current_user: User = Depends(get_current_user),
    service: ExpenseService = Depends(get_expense_service),
    audit: AuditService = Depends(get_audit_service),
):
    try:
        expense, replayed = service.create_expense_idempotent(
            user_id=current_user.id,
            payload=payload,
            idempotency_key=idempotency_key,
        )
    except ExpenseSourceNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Source record not found"
        ) from None
    except ExpenseTripAssignmentError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Trip not found"
        ) from None
    except (ExpenseSourceTypeError, ExpenseTripConflictError, InvalidExpenseAmountsError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc) or "Invalid expense"
        ) from None
    except IdempotencyConflictError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Idempotency key reused with a different request",
        ) from None
    except IdempotencyInProgressError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Request is still in progress"
        ) from None
    except IdempotencyResultGoneError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The result of this key was deleted",
        ) from None
    if not replayed:
        audit.log(
            action=AuditAction.CREATE_RECORD,
            user_id=current_user.id,
            resource_type="expense",
            resource_id=str(expense.id),
            meta={"category": expense.category, "amount": str(expense.amount)},
            request=request,
        )
    return expense


@router.get("/{expense_id}", response_model=ExpenseRead)
def get_expense(
    expense_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: ExpenseService = Depends(get_expense_service),
):
    try:
        return service.get_expense(user_id=current_user.id, expense_id=expense_id)
    except ExpenseNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found") from None


@router.patch("/{expense_id}", response_model=ExpenseRead)
def update_expense(
    expense_id: uuid.UUID,
    payload: ExpenseUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    service: ExpenseService = Depends(get_expense_service),
    audit: AuditService = Depends(get_audit_service),
):
    try:
        expense = service.update_expense(
            user_id=current_user.id, expense_id=expense_id, payload=payload
        )
    except ExpenseSourceNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Source record not found"
        ) from None
    except ExpenseTripAssignmentError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Trip not found"
        ) from None
    except (ExpenseSourceTypeError, ExpenseTripConflictError, InvalidExpenseAmountsError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc) or "Invalid expense"
        ) from None
    except ExpenseNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found") from None
    audit.log(
        action=AuditAction.UPDATE_RECORD,
        user_id=current_user.id,
        resource_type="expense",
        resource_id=str(expense.id),
        meta={"changed_fields": sorted(payload.model_dump(exclude_unset=True).keys())},
        request=request,
    )
    return expense


@router.delete("/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_expense(
    expense_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    service: ExpenseService = Depends(get_expense_service),
    audit: AuditService = Depends(get_audit_service),
) -> None:
    try:
        service.delete_expense(user_id=current_user.id, expense_id=expense_id)
    except ExpenseNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found") from None
    audit.log(
        action=AuditAction.DELETE_RECORD,
        user_id=current_user.id,
        resource_type="expense",
        resource_id=str(expense_id),
        request=request,
    )
