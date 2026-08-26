"""Batching and retry helpers for embedding providers."""

from __future__ import annotations

import time
from collections.abc import Iterable

from app.core.config import Settings, get_settings
from app.embeddings.models import EmbeddingInput, EmbeddingVector
from app.embeddings.providers import EmbeddingProvider


def batched(items: list[EmbeddingInput], size: int) -> Iterable[list[EmbeddingInput]]:
    if size <= 0:
        raise ValueError("batch size must be positive")
    for start in range(0, len(items), size):
        yield items[start : start + size]


class BatchEmbedder:
    def __init__(
        self,
        provider: EmbeddingProvider,
        settings: Settings | None = None,
    ) -> None:
        self.provider = provider
        self.settings = settings or get_settings()

    def embed(self, inputs: list[EmbeddingInput]) -> list[EmbeddingVector]:
        limit = min(self.settings.embedding_batch_size, self.provider.info.max_batch_size)
        vectors: list[EmbeddingVector] = []
        for i, batch in enumerate(batched(inputs, limit)):
            if i > 0:
                time.sleep(1.0)
            vectors.extend(self._embed_with_retries(batch))
        return vectors

    def _embed_with_retries(self, batch: list[EmbeddingInput]) -> list[EmbeddingVector]:
        attempts = max(1, self.settings.embedding_max_retries)
        last_exc: Exception | None = None
        for attempt in range(attempts):
            try:
                vectors = self.provider.embed(batch)
                if [item.id for item in vectors] != [item.id for item in batch]:
                    raise ValueError("embedding provider returned vectors out of order")
                expected = self.provider.info.dimensions
                if any(len(item.vector) != expected for item in vectors):
                    raise ValueError("embedding provider returned an unexpected dimension")
                return vectors
            except Exception as exc:
                last_exc = exc
                if attempt + 1 == attempts:
                    break
                sleep_time = (5.0 * (2**attempt)) if "429" in str(exc) else max(3.0, self.settings.embedding_retry_base_seconds * (2**attempt))
                time.sleep(sleep_time)
        assert last_exc is not None
        raise last_exc
