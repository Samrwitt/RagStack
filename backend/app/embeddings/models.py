"""Embedding provider data contracts."""

from __future__ import annotations

from dataclasses import dataclass

EMBEDDING_RECORD_STATUS_EMBEDDED = "EMBEDDED"
EMBEDDING_RECORD_STATUS_INDEXED = "INDEXED"
EMBEDDING_RECORD_STATUS_FAILED = "FAILED"
EMBEDDING_RECORD_STATUS_DELETED = "DELETED"


@dataclass(frozen=True, slots=True)
class EmbeddingInput:
    id: str
    text: str


@dataclass(frozen=True, slots=True)
class EmbeddingVector:
    id: str
    vector: list[float]


@dataclass(frozen=True, slots=True)
class EmbeddingProviderInfo:
    provider: str
    model: str
    dimensions: int
    max_batch_size: int
    embedding_version: int
