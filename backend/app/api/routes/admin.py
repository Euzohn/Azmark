import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.api.deps import (
    get_admin_service,
    get_audit_service,
    get_current_admin,
    get_system_settings_service,
)
from app.models.audit_log import AuditAction
from app.models.user import User
from app.schemas.admin import (
    AdminAuditLogList,
    AdminAuditLogRead,
    AdminSystemRead,
    AdminUserCreate,
    AdminUserList,
    AdminUserRead,
    AdminUserUpdate,
)
from app.schemas.system_setting import (
    AdminSettingsRead,
    AdminSettingsUpdate,
    AdminTestEmailRequest,
    AdminTestEmailResponse,
)
from app.services.admin import (
    AdminSelfLockoutError,
    AdminService,
    AdminUserExistsError,
    AdminUserNotFoundError,
)
from app.services.audit import AuditService
from app.services.system_setting import SmtpDeliveryError, SystemSettingsService

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


@router.post("/users", response_model=AdminUserRead, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: AdminUserCreate,
    request: Request,
    current_admin: User = Depends(get_current_admin),
    service: AdminService = Depends(get_admin_service),
    audit: AuditService = Depends(get_audit_service),
) -> AdminUserRead:
    try:
        user = service.create_user(
            username=payload.username,
            password=payload.password,
            email=payload.email,
            display_name=payload.display_name,
            role=payload.role,
        )
    except AdminUserExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from None
    audit.log(
        action=AuditAction.ADMIN_CREATE_USER,
        user_id=current_admin.id,
        resource_type="user",
        resource_id=str(user.id),
        meta={"username": payload.username},
        request=request,
    )
    return service.read_user(user)


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
    request_id: str | None = None,
    ip: str | None = None,
    _: User = Depends(get_current_admin),
    audit: AuditService = Depends(get_audit_service),
) -> AdminAuditLogList:
    items, total = audit.list_all(
        page=page,
        page_size=page_size,
        user_id=user_id,
        action=action,
        request_id=request_id,
        ip=ip,
    )
    return AdminAuditLogList(
        items=[
            AdminAuditLogRead(
                id=item.id,
                user_id=item.user_id,
                action=item.action,
                resource_type=item.resource_type,
                resource_id=item.resource_id,
                meta=item.meta,
                ip=item.ip,
                ip_hash=item.ip_hash,
                user_agent=item.user_agent,
                request_id=item.request_id,
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


@router.get("/settings", response_model=AdminSettingsRead)
def read_settings(
    _: User = Depends(get_current_admin),
    service: SystemSettingsService = Depends(get_system_settings_service),
) -> AdminSettingsRead:
    return service.read()


@router.patch("/settings", response_model=AdminSettingsRead)
def update_settings(
    payload: AdminSettingsUpdate,
    request: Request,
    current_admin: User = Depends(get_current_admin),
    service: SystemSettingsService = Depends(get_system_settings_service),
    audit: AuditService = Depends(get_audit_service),
) -> AdminSettingsRead:
    updated = service.update(payload)
    # Field names only — never values; SMTP credentials must not reach the log.
    fields = sorted(payload.model_dump(exclude_unset=True).keys())
    audit.log(
        action=AuditAction.ADMIN_UPDATE_SETTINGS,
        user_id=current_admin.id,
        meta={"fields": fields},
        request=request,
    )
    return updated


@router.post("/settings/test-email", response_model=AdminTestEmailResponse)
def test_email(
    payload: AdminTestEmailRequest,
    current_admin: User = Depends(get_current_admin),
    service: SystemSettingsService = Depends(get_system_settings_service),
) -> AdminTestEmailResponse:
    to = (payload.to or "").strip() or (current_admin.email or "").strip()
    if not to:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide a recipient address (or set your account email first)",
        )
    try:
        service.send_test_email(to)
    except SmtpDeliveryError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from None
    return AdminTestEmailResponse(ok=True)
