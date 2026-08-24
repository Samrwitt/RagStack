"""Retrieval contracts shared by dense, sparse, and hybrid search."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from uuid import UUID


class RetrievalMode(StrEnum):
    DENSE = "dense"
    SPARSE = "sparse"
    HYBRID = "hybrid"


@dataclass(frozen=True, slots=True)
class ACLContext:
    user_id: str | None = None
    group_ids: frozenset[str] = frozenset()


@dataclass(frozen=True, slots=True)
class RetrievalFilters:
    organization_id: UUID
    workspace_id: UUID | None = None
    source_connection_id: UUID | None = None
    source_type: str | None = None
    document_ids: tuple[UUID, ...] = ()
    language: str | None = None


@dataclass(frozen=True, slots=True)
class RetrievalRequest:
    query: str
    filters: RetrievalFilters
    acl: ACLContext = field(default_factory=ACLContext)
    mode: RetrievalMode = RetrievalMode.HYBRID
    top_k: int = 10
    candidate_k: int = 50
    rerank: bool = False
    context_token_budget: int | None = None


@dataclass(frozen=True, slots=True)
class RetrievalHit:
    chunk_id: UUID
    document_id: UUID
    version_id: UUID
    score: float
    rank: int
    text: str
    title: str
    source_type: str
    source_url: str | None
    page: int | None
    section: str | None
    metadata: dict
    scores: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SelectedContext:
    hit: RetrievalHit
    token_count: int
