from fastapi import APIRouter, Depends, Query

from app.api.deps import get_audit_service, get_current_user
from app.models.user import User
from app.schemas.audit import AuditLogList
from app.services.audit import AuditService

router = APIRouter(prefix="/audit-logs", tags=["audit"])


@router.get("", response_model=AuditLogList)
def list_audit_logs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    audit: AuditService = Depends(get_audit_service),
) -> AuditLogList:
    items, total = audit.list_for_user(user_id=current_user.id, page=page, page_size=page_size)
    return AuditLogList(items=items, total=total, page=page, page_size=page_size)
