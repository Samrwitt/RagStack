"""Pydantic schemas for retrieval endpoints."""

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    mode: Literal["sparse", "hybrid", "dense"] = "hybrid"
    top_k: int = Field(default=10, ge=1, le=50)
    candidate_k: int = Field(default=50, ge=1, le=200)
    workspace_id: UUID | None = None
    source_connection_id: UUID | None = None
    source_type: str | None = None
    document_ids: list[UUID] = Field(default_factory=list)
    language: str | None = None
    user_id: str | None = None
    group_ids: list[str] = Field(default_factory=list)
    rerank: bool = False
    context_token_budget: int | None = Field(default=None, ge=1, le=32000)


class SearchHitRead(BaseModel):
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
    metadata: dict[str, Any]
    scores: dict[str, float]


class SearchResponse(BaseModel):
    query: str
    mode: str
    hits: list[SearchHitRead]
    context: list[SearchHitRead] = Field(default_factory=list)
