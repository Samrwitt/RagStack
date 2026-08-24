"""Canonical documents and their immutable versions."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.block import DocumentBlock
from app.models.chunk import DocumentChunk
from app.models.enums import DocumentState

if TYPE_CHECKING:
    from app.models.source import SourceConnection


class Document(TimestampMixin, Base):
    """Stable identity is the primary key — never a random UUID per discovery."""

    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint("source_connection_id", "source_id", name="uq_document_source_item"),
        Index("ix_documents_org_state", "organization_id", "current_state"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    workspace_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False, index=True
    )
    source_connection_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("source_connections.id"), nullable=False
    )
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_id: Mapped[str] = mapped_column(String(1024), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    current_version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    current_state: Mapped[str] = mapped_column(
        String(32), default=DocumentState.DISCOVERED.value, nullable=False
    )
    last_successful_state: Mapped[str | None] = mapped_column(String(32), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    extra_metadata: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, nullable=False)
    permissions: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    raw_object_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    language: Mapped[str | None] = mapped_column(String(16), nullable=True)
    canonical_document_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("documents.id"), nullable=True, index=True
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    source_connection: Mapped[SourceConnection] = relationship(back_populates="documents")
    versions: Mapped[list[DocumentVersion]] = relationship(
        back_populates="document", order_by="DocumentVersion.version_number"
    )
    blocks: Mapped[list[DocumentBlock]] = relationship(
        back_populates="document", order_by="DocumentBlock.ordinal"
    )
    chunks: Mapped[list[DocumentChunk]] = relationship(
        back_populates="document", order_by="DocumentChunk.ordinal"
    )


class DocumentVersion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "document_versions"
    __table_args__ = (
        UniqueConstraint("document_id", "version_number", name="uq_document_version_number"),
    )

    document_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_object_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    original_filename: Mapped[str | None] = mapped_column(String(512), nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    extra_metadata: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, nullable=False)
    parser_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    parser_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    used_ocr: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    parsed_block_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    parse_warnings: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    parsed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    language: Mapped[str | None] = mapped_column(String(16), nullable=True)
    normalized_content_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True
    )
    simhash: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    normalizer_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    normalizer_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    normalized_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    duplicate_kind: Mapped[str | None] = mapped_column(String(16), nullable=True)
    chunk_strategy: Mapped[str | None] = mapped_column(String(32), nullable=True)
    chunker_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    chunked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    document: Mapped[Document] = relationship(back_populates="versions")
    blocks: Mapped[list[DocumentBlock]] = relationship(
        back_populates="version", order_by="DocumentBlock.ordinal"
    )
    chunks: Mapped[list[DocumentChunk]] = relationship(
        back_populates="version", order_by="DocumentChunk.ordinal"
    )
