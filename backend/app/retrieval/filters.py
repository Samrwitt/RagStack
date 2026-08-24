"""Metadata filter helpers for retrieval queries."""

from __future__ import annotations

from sqlalchemy import Select

from app.models.document import Document, DocumentVersion
from app.retrieval.models import RetrievalFilters


def apply_document_filters(stmt: Select, filters: RetrievalFilters) -> Select:
    stmt = stmt.where(
        Document.organization_id == filters.organization_id,
        DocumentVersion.is_current.is_(True),
        Document.deleted_at.is_(None),
    )
    if filters.workspace_id is not None:
        stmt = stmt.where(Document.workspace_id == filters.workspace_id)
    if filters.source_connection_id is not None:
        stmt = stmt.where(Document.source_connection_id == filters.source_connection_id)
    if filters.source_type is not None:
        stmt = stmt.where(Document.source_type == filters.source_type)
    if filters.document_ids:
        stmt = stmt.where(Document.id.in_(filters.document_ids))
    if filters.language is not None:
        stmt = stmt.where(DocumentVersion.language == filters.language)
    return stmt
