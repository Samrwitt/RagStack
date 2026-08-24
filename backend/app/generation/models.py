"""Grounded generation contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from uuid import UUID

from app.retrieval.models import RetrievalHit


class EvidenceStatus(StrEnum):
    GROUNDED = "grounded"
    INSUFFICIENT = "insufficient_evidence"


@dataclass(frozen=True, slots=True)
class ChatMessage:
    role: str
    content: str


@dataclass(frozen=True, slots=True)
class Citation:
    index: int
    document_id: UUID
    version_id: UUID
    chunk_id: UUID
    title: str
    source_type: str
    source_url: str | None
    page: int | None
    section: str | None


@dataclass(frozen=True, slots=True)
class GroundedAnswer:
    answer: str
    evidence_status: EvidenceStatus
    citations: list[Citation] = field(default_factory=list)
    context: list[RetrievalHit] = field(default_factory=list)
    retrieval_query: str = ""
