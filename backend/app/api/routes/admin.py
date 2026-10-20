import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.api.deps import get_admin_service, get_audit_service, get_current_admin
from app.models.audit_log import AuditAction
from app.models.user import User
from app.schemas.admin import (
    AdminAuditLogList,
    AdminAuditLogRead,
    AdminSystemRead,
    AdminUserList,
    AdminUserRead,
    AdminUserUpdate,
)
from app.services.admin import AdminSelfLockoutError, AdminService, AdminUserNotFoundError
from app.services.audit import AuditService

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=AdminUserList)
def list_users(
    search: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    _: User = Depends(get_current_admin),
    service: AdminService = Depends(get_admin_service),
) -> AdminUserList:
    items, total = service.list_users(search=search, page=page, page_size=page_size)
    return AdminUserList(items=items, total=total, page=page, page_size=page_size)


@router.patch("/users/{user_id}", response_model=AdminUserRead)
def update_user(
    user_id: uuid.UUID,
    payload: AdminUserUpdate,
    request: Request,
    current_admin: User = Depends(get_current_admin),
    service: AdminService = Depends(get_admin_service),
    audit: AuditService = Depends(get_audit_service),
) -> AdminUserRead:
    try:
        user, fields = service.update_user(actor=current_admin, user_id=user_id, payload=payload)
    except AdminUserNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found") from None
    except AdminSelfLockoutError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot demote or disable your own account",
        ) from None

    if fields:
        audit.log(
            action=AuditAction.ADMIN_UPDATE_USER,
            user_id=current_admin.id,
            resource_type="user",
            resource_id=str(user.id),
            meta={"fields": fields},
            request=request,
        )
    return user


@router.get("/logs", response_model=AdminAuditLogList)
def list_logs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    user_id: uuid.UUID | None = None,
    action: str | None = None,
    _: User = Depends(get_current_admin),
    audit: AuditService = Depends(get_audit_service),
) -> AdminAuditLogList:
    items, total = audit.list_all(page=page, page_size=page_size, user_id=user_id, action=action)
    return AdminAuditLogList(
        items=[
            AdminAuditLogRead(
                id=item.id,
                user_id=item.user_id,
                action=item.action,
                resource_type=item.resource_type,
                resource_id=item.resource_id,
                meta=item.meta,
                created_at=item.created_at,
            )
            for item in items
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/system", response_model=AdminSystemRead)
def system(
    _: User = Depends(get_current_admin),
    service: AdminService = Depends(get_admin_service),
) -> AdminSystemRead:
    return service.system()
