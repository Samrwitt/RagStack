"""Embedding provider abstraction and local deterministic implementation."""

from __future__ import annotations

import hashlib
import math
from typing import Protocol

from app.core.config import Settings, get_settings
from app.embeddings.models import EmbeddingInput, EmbeddingProviderInfo, EmbeddingVector


class EmbeddingProvider(Protocol):
    info: EmbeddingProviderInfo

    def embed(self, inputs: list[EmbeddingInput]) -> list[EmbeddingVector]:
        """Return one vector per input, preserving input order."""


class DeterministicEmbeddingProvider:
    """Stable dev/test provider that maps text to normalized hash-derived vectors."""

    def __init__(self, settings: Settings | None = None) -> None:
        cfg = settings or get_settings()
        self.info = EmbeddingProviderInfo(
            provider="deterministic",
            model=cfg.embedding_model,
            dimensions=cfg.embedding_dimension,
            max_batch_size=cfg.embedding_batch_size,
            embedding_version=cfg.embedding_version,
        )

    def embed(self, inputs: list[EmbeddingInput]) -> list[EmbeddingVector]:
        return [
            EmbeddingVector(id=item.id, vector=self._vectorize(item.text))
            for item in inputs
        ]

    def _vectorize(self, text: str) -> list[float]:
        values: list[float] = []
        seed = text.encode("utf-8")
        counter = 0
        while len(values) < self.info.dimensions:
            digest = hashlib.sha256(seed + counter.to_bytes(4, "big")).digest()
            values.extend((byte / 127.5) - 1.0 for byte in digest)
            counter += 1
        vector = values[: self.info.dimensions]
        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return vector
        return [value / norm for value in vector]


def get_embedding_provider(settings: Settings | None = None) -> EmbeddingProvider:
    cfg = settings or get_settings()
    if cfg.embedding_provider == "deterministic":
        return DeterministicEmbeddingProvider(cfg)
    raise ValueError(f"unsupported embedding provider: {cfg.embedding_provider}")
