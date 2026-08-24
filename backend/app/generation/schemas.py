"""Pydantic schemas for grounded chat endpoints."""

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.generation.models import EvidenceStatus


class ChatMessageRead(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str = Field(min_length=1)


class ChatRequest(BaseModel):
    question: str = Field(min_length=1)
    history: list[ChatMessageRead] = Field(default_factory=list)
    mode: Literal["dense", "sparse", "hybrid"] = "hybrid"
    top_k: int = Field(default=8, ge=1, le=30)
    candidate_k: int = Field(default=50, ge=1, le=200)
    workspace_id: UUID | None = None
    source_connection_id: UUID | None = None
    source_type: str | None = None
    document_ids: list[UUID] = Field(default_factory=list)
    language: str | None = None


class CitationRead(BaseModel):
    index: int
    document_id: UUID
    version_id: UUID
    chunk_id: UUID
    title: str
    source_type: str
    source_url: str | None
    page: int | None
    section: str | None


class ChatResponse(BaseModel):
    answer: str
    evidence_status: EvidenceStatus
    citations: list[CitationRead]
    retrieval_query: str
    context: list[dict[str, Any]]
