"""Recorded exact and near-duplicate relationships. Never a silent delete."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import DuplicateKind


class DocumentDuplicate(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "document_duplicates"
    __table_args__ = (
        UniqueConstraint(
            "canonical_version_id",
            "duplicate_version_id",
            "kind",
            name="uq_document_duplicate_pair",
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    canonical_document_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False, index=True
    )
    duplicate_document_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False, index=True
    )
    canonical_version_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("document_versions.id"), nullable=False
    )
    duplicate_version_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("document_versions.id"), nullable=False
    )
    kind: Mapped[str] = mapped_column(
        String(16), default=DuplicateKind.EXACT.value, nullable=False
    )
    score: Mapped[float] = mapped_column(Float, nullable=False)
