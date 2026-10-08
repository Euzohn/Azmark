from fastapi import APIRouter, Depends, HTTPException, Request, status

import app.providers as providers
from app.api.deps import get_audit_service, get_current_user, get_provider_keys_service
from app.models.audit_log import AuditAction
from app.models.user import User
from app.schemas.settings import ProviderKeysRead, ProviderKeyStatus, ProviderKeyWrite
from app.services.audit import AuditService
from app.services.provider_keys import ProviderKeyStore

router = APIRouter(prefix="/settings", tags=["settings"])


def _ensure_provider(provider: str) -> None:
    if provider not in providers.REGISTERED_PROVIDERS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown provider")


@router.get("/provider-keys", response_model=ProviderKeysRead)
def list_provider_keys(
    current_user: User = Depends(get_current_user),
    keys: ProviderKeyStore = Depends(get_provider_keys_service),
) -> ProviderKeysRead:
    configured = keys.get_decrypted(user_id=current_user.id)
    return ProviderKeysRead(
        providers=[
            ProviderKeyStatus(provider=name, configured=name in configured)
            for name in providers.provider_names()
        ]
    )


@router.put("/provider-keys/{provider}", response_model=ProviderKeyStatus)
def upsert_provider_key(
    provider: str,
    payload: ProviderKeyWrite,
    request: Request,
    current_user: User = Depends(get_current_user),
    keys: ProviderKeyStore = Depends(get_provider_keys_service),
    audit: AuditService = Depends(get_audit_service),
) -> ProviderKeyStatus:
    _ensure_provider(provider)
    keys.upsert(user_id=current_user.id, provider=provider, api_key=payload.api_key)
    audit.log(
        action=AuditAction.UPDATE_RECORD,
        user_id=current_user.id,
        resource_type="provider_key",
        resource_id=provider,
        request=request,
    )
    return ProviderKeyStatus(provider=provider, configured=True)


@router.delete("/provider-keys/{provider}", status_code=status.HTTP_204_NO_CONTENT)
def delete_provider_key(
    provider: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    keys: ProviderKeyStore = Depends(get_provider_keys_service),
    audit: AuditService = Depends(get_audit_service),
) -> None:
    _ensure_provider(provider)
    keys.delete(user_id=current_user.id, provider=provider)
    audit.log(
        action=AuditAction.DELETE_RECORD,
        user_id=current_user.id,
        resource_type="provider_key",
        resource_id=provider,
        request=request,
    )
