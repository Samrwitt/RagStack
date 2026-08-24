"""Persisted chunks for a document version (retrieval units)."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.document import Document, DocumentVersion


class DocumentChunk(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "document_chunks"
    __table_args__ = (
        UniqueConstraint("version_id", "ordinal", name="uq_document_chunk_ordinal"),
        Index("ix_document_chunks_document_id", "document_id"),
        Index("ix_document_chunks_version_id", "version_id"),
        Index("ix_document_chunks_parent_chunk_id", "parent_chunk_id"),
    )

    document_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False
    )
    version_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("document_versions.id"), nullable=False
    )
    parent_chunk_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("document_chunks.id"), nullable=True
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    section: Mapped[str | None] = mapped_column(String(512), nullable=True)
    strategy: Mapped[str] = mapped_column(String(32), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False, default="leaf")
    extra: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    document: Mapped[Document] = relationship(back_populates="chunks")
    version: Mapped[DocumentVersion] = relationship(back_populates="chunks")
