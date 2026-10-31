import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.deps import get_access_token_service, get_audit_service, get_current_user
from app.models.audit_log import AuditAction
from app.models.user import User
from app.schemas.access_token import (
    AccessTokenCreate,
    AccessTokenCreated,
    AccessTokenList,
    AccessTokenRead,
)
from app.services.access_token import AccessTokenNotFoundError, AccessTokenService
from app.services.audit import AuditService

router = APIRouter(prefix="/tokens", tags=["tokens"])


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Token not found")


@router.get("", response_model=AccessTokenList)
def list_access_tokens(
    current_user: User = Depends(get_current_user),
    service: AccessTokenService = Depends(get_access_token_service),
) -> AccessTokenList:
    return AccessTokenList(items=service.list_for_user(user_id=current_user.id))


@router.post("", response_model=AccessTokenCreated, status_code=status.HTTP_201_CREATED)
def create_access_token(
    payload: AccessTokenCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    service: AccessTokenService = Depends(get_access_token_service),
    audit: AuditService = Depends(get_audit_service),
) -> AccessTokenCreated:
    record, secret = service.create(
        user_id=current_user.id,
        name=payload.name,
        scope=payload.scope,
        expires_in_days=payload.expires_in_days,
    )
    audit.log(
        action=AuditAction.CREATE_ACCESS_TOKEN,
        user_id=current_user.id,
        resource_type="access_token",
        resource_id=str(record.id),
        # The secret itself must never be logged (spec #45, #75).
        meta={"name": record.name, "scope": record.scope},
        request=request,
    )
    return AccessTokenCreated(
        **AccessTokenRead.model_validate(record).model_dump(),
        token=secret,
    )


@router.post("/{token_id}/revoke", status_code=status.HTTP_204_NO_CONTENT)
def revoke_access_token(
    token_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    service: AccessTokenService = Depends(get_access_token_service),
    audit: AuditService = Depends(get_audit_service),
) -> None:
    try:
        record = service.revoke(user_id=current_user.id, token_id=token_id)
    except AccessTokenNotFoundError:
        raise _not_found() from None
    audit.log(
        action=AuditAction.REVOKE_ACCESS_TOKEN,
        user_id=current_user.id,
        resource_type="access_token",
        resource_id=str(record.id),
        meta={"name": record.name},
        request=request,
    )


@router.delete("/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_access_token(
    token_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    service: AccessTokenService = Depends(get_access_token_service),
    audit: AuditService = Depends(get_audit_service),
) -> None:
    try:
        service.delete(user_id=current_user.id, token_id=token_id)
    except AccessTokenNotFoundError:
        raise _not_found() from None
    audit.log(
        action=AuditAction.DELETE_ACCESS_TOKEN,
        user_id=current_user.id,
        resource_type="access_token",
        resource_id=str(token_id),
        request=request,
    )
