"""Import / export endpoints (spec #42/#43). Fully user-scoped (#57)."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile

from app.api.deps import (
    get_audit_service,
    get_current_user,
    get_data_source_service,
    get_data_transfer_service,
)
from app.models.audit_log import AuditAction
from app.models.user import User
from app.schemas.data_transfer import ImportPreview, ImportResult
from app.services.audit import AuditService
from app.services.data_source import DataSourceService
from app.services.data_transfer import DataTransferService

router = APIRouter(tags=["data"])


def _decode_file(file: UploadFile) -> str:
    data = file.file.read()
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(status_code=422, detail="File must be UTF-8 encoded") from None


def _infer_format(filename: str | None, content: str) -> str:
    if filename:
        lowered = filename.lower()
        if lowered.endswith(".json"):
            return "json"
        if lowered.endswith(".csv"):
            return "csv"
    stripped = content.lstrip()
    if stripped.startswith("{") or stripped.startswith("["):
        return "json"
    return "csv"


@router.get("/export")
def export_data(
    format: Literal["json", "csv"] = "json",
    include_sensitive: bool = False,
    request: Request = None,
    current_user: User = Depends(get_current_user),
    service: DataTransferService = Depends(get_data_transfer_service),
    audit: AuditService = Depends(get_audit_service),
) -> Response:
    if format == "csv":
        content = service.export_csv(user_id=current_user.id, include_sensitive=include_sensitive)
        media_type = "text/csv"
        filename = "azmark-export.csv"
    else:
        content = service.export_json(user_id=current_user.id, include_sensitive=include_sensitive)
        media_type = "application/json"
        filename = "azmark-export.json"
    audit.log(
        action=AuditAction.EXPORT,
        user_id=current_user.id,
        resource_type="data",
        meta={"format": format, "include_sensitive": include_sensitive},
        request=request,
    )
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/import/template")
def import_template(
    format: Literal["json", "csv"] = "csv",
    service: DataTransferService = Depends(get_data_transfer_service),
) -> Response:
    content = service.template(format=format)
    return Response(
        content=content,
        media_type="text/csv" if format == "csv" else "application/json",
        headers={"Content-Disposition": f'attachment; filename="azmark-import-template.{format}"'},
    )


@router.post("/import/preview", response_model=ImportPreview)
async def preview_import(
    file: Annotated[UploadFile, File()],
    format: Annotated[str | None, Form()] = None,
    mapping: Annotated[str | None, Form()] = None,
    current_user: User = Depends(get_current_user),
    service: DataTransferService = Depends(get_data_transfer_service),
) -> ImportPreview:
    content = _decode_file(file)
    fmt = format or _infer_format(file.filename, content)
    mapping_dict = _parse_mapping(mapping)
    return service.preview(
        user_id=current_user.id, format=fmt, content=content, mapping=mapping_dict
    )


@router.post("/import", response_model=ImportResult)
async def import_data(
    request: Request,
    file: Annotated[UploadFile, File()],
    format: Annotated[str | None, Form()] = None,
    mapping: Annotated[str | None, Form()] = None,
    current_user: User = Depends(get_current_user),
    service: DataTransferService = Depends(get_data_transfer_service),
    sources: DataSourceService = Depends(get_data_source_service),
    audit: AuditService = Depends(get_audit_service),
) -> ImportResult:
    content = _decode_file(file)
    fmt = format or _infer_format(file.filename, content)
    mapping_dict = _parse_mapping(mapping)
    result = service.import_records(
        user_id=current_user.id, format=fmt, content=content, mapping=mapping_dict
    )
    sources.record(
        user_id=current_user.id,
        source_type="import",
        source_name=file.filename or f"import.{fmt}",
        provider=fmt,
        confidence=1.0,
        metadata={
            "format": fmt,
            "imported": result.imported,
            "skipped_duplicates": result.skipped_duplicates,
            "failed": result.failed,
            "trips_created": result.trips_created,
        },
    )
    audit.log(
        action=AuditAction.IMPORT,
        user_id=current_user.id,
        resource_type="data",
        meta={
            "format": fmt,
            "imported": result.imported,
            "skipped_duplicates": result.skipped_duplicates,
            "failed": result.failed,
            "trips_created": result.trips_created,
        },
        request=request,
    )
    return result


def _parse_mapping(raw: str | None) -> dict[str, str] | None:
    if not raw:
        return None
    import json

    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        raise HTTPException(status_code=422, detail="mapping must be a JSON object") from None
    if not isinstance(value, dict):
        raise HTTPException(status_code=422, detail="mapping must be a JSON object") from None
    return {str(k): str(v) for k, v in value.items()}
