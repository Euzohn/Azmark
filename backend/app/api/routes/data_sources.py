"""DataSource endpoints (spec #22, #37, #57)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.api.deps import get_audit_service, get_current_user, get_data_source_service
from app.models.audit_log import AuditAction
from app.models.user import User
from app.schemas.data_source import DataSourceList, DataSourceRead
from app.services.audit import AuditService
from app.services.data_source import DataSourceService

router = APIRouter(prefix="/data-sources", tags=["data"])


@router.get("", response_model=DataSourceList)
def list_data_sources(
    source_type: Annotated[str | None, Query(max_length=20)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    current_user: User = Depends(get_current_user),
    service: DataSourceService = Depends(get_data_source_service),
) -> DataSourceList:
    items, total = service.list(
        user_id=current_user.id,
        source_type=source_type,
        limit=limit,
    )
    return DataSourceList(items=items, total=total)


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_data_source(
    source_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    service: DataSourceService = Depends(get_data_source_service),
    audit: AuditService = Depends(get_audit_service),
) -> None:
    if not service.delete(user_id=current_user.id, source_id=source_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    audit.log(
        action=AuditAction.DELETE_RECORD,
        user_id=current_user.id,
        resource_type="data_source",
        resource_id=str(source_id),
        request=request,
    )


@router.get("/{source_id}", response_model=DataSourceRead)
def get_data_source(
    source_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: DataSourceService = Depends(get_data_source_service),
) -> DataSourceRead:
    source = service.get(user_id=current_user.id, source_id=source_id)
    if source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return DataSourceRead.model_validate(source)
