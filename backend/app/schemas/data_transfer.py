"""Schemas for import/export endpoints (spec #42/#43)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

ExportFormat = Literal["json", "csv"]


class ImportRowError(BaseModel):
    row: int
    field: str | None = None
    message: str


class ImportDuplicate(BaseModel):
    row: int
    signature: str


class ImportPreview(BaseModel):
    format: str
    columns: list[str]
    field_mapping: dict[str, str]
    target_fields: list[str] = Field(default_factory=list)
    total: int
    valid: int
    duplicate_count: int
    error_count: int
    errors: list[ImportRowError]
    duplicates: list[ImportDuplicate]
    rows: list[dict] = []
    truncated: bool = False


class ImportResult(BaseModel):
    imported: int
    skipped_duplicates: int
    failed: int
    trips_created: int
    errors: list[ImportRowError] = Field(default_factory=list)
