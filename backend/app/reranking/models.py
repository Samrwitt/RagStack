"""Reranking provider contracts."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class RerankCandidate:
    chunk_id: UUID
    text: str
    rank: int
    score: float


@dataclass(frozen=True, slots=True)
class RerankResult:
    chunk_id: UUID
    score: float
