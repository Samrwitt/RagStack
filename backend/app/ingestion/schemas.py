"""Pydantic models for ingestion API responses."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class SourceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    workspace_id: UUID | None = None
    source_type: str = "file_upload"
    config: dict[str, Any] = Field(default_factory=dict)


class SourceRead(ORMModel):
    id: UUID
    organization_id: UUID
    workspace_id: UUID
    name: str
    source_type: str
    status: str
    document_count: int
    last_sync_at: datetime | None
    last_error: str | None
    checkpoint: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class DocumentVersionRead(ORMModel):
    id: UUID
    version_number: int
    content_hash: str
    raw_object_key: str
    mime_type: str | None
    size_bytes: int
    original_filename: str | None
    is_current: bool
    retrieved_at: datetime
    parser_name: str | None = None
    parser_version: int | None = None
    used_ocr: bool = False
    parsed_block_count: int = 0
    parse_warnings: list[Any] = Field(default_factory=list)
    parsed_at: datetime | None = None
    language: str | None = None
    normalized_content_hash: str | None = None
    simhash: int | None = None
    normalizer_name: str | None = None
    normalizer_version: int | None = None
    normalized_at: datetime | None = None
    duplicate_kind: str | None = None


class DocumentRead(ORMModel):
    id: UUID
    organization_id: UUID
    workspace_id: UUID
    source_connection_id: UUID
    source_type: str
    source_id: str
    title: str
    mime_type: str | None
    source_url: str | None
    current_version: int
    content_hash: str | None
    current_state: str
    last_successful_state: str | None
    last_error: str | None
    retry_count: int
    raw_object_key: str | None
    permissions: dict[str, Any]
    metadata: dict[str, Any] = Field(validation_alias="extra_metadata")
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None
    language: str | None = None
    canonical_document_id: UUID | None = None


class JobRead(ORMModel):
    id: UUID
    organization_id: UUID
    source_connection_id: UUID | None
    document_id: UUID | None
    job_type: str
    status: str
    attempt: int
    last_error: str | None
    staging_object_key: str | None
    started_at: datetime | None
    finished_at: datetime | None
    stats: dict[str, Any]
    created_at: datetime


class UploadResult(BaseModel):
    unchanged: bool
    document: DocumentRead
    job: JobRead


class BlockRead(BaseModel):
    id: UUID
    ordinal: int
    type: str
    text: str
    normalized_text: str | None = None
    dropped: bool = False
    drop_reason: str | None = None
    level: int | None = None
    page: int | None = None
    section: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ParsedBlocksRead(BaseModel):
    document_id: UUID
    version_id: UUID
    version_number: int
    parser_name: str | None
    parser_version: int | None
    used_ocr: bool
    title: str
    language: str | None = None
    normalized_content_hash: str | None = None
    warnings: list[Any] = Field(default_factory=list)
    blocks: list[BlockRead]


class DuplicateRead(ORMModel):
    id: UUID
    canonical_document_id: UUID
    duplicate_document_id: UUID
    canonical_version_id: UUID
    duplicate_version_id: UUID
    kind: str
    score: float
    created_at: datetime
