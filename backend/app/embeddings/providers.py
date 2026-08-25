"""Embedding provider abstraction and local deterministic implementation."""

from __future__ import annotations

import hashlib
import math
from typing import Protocol

import httpx

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


class OpenAIEmbeddingProvider:
    """Embedding provider backed by the OpenAI-compatible embeddings API."""

    def __init__(self, settings: Settings | None = None) -> None:
        cfg = settings or get_settings()
        if not cfg.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required when EMBEDDING_PROVIDER=openai")
        self.settings = cfg
        self.info = EmbeddingProviderInfo(
            provider="openai",
            model=cfg.embedding_model,
            dimensions=cfg.embedding_dimension,
            max_batch_size=cfg.embedding_batch_size,
            embedding_version=cfg.embedding_version,
        )

    def embed(self, inputs: list[EmbeddingInput]) -> list[EmbeddingVector]:
        if not inputs:
            return []
        response = httpx.post(
            f"{self.settings.openai_base_url.rstrip('/')}/embeddings",
            headers={
                "Authorization": f"Bearer {self.settings.openai_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.info.model,
                "input": [item.text for item in inputs],
                "dimensions": self.info.dimensions,
                "encoding_format": "float",
            },
            timeout=self.settings.openai_timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        data = sorted(payload["data"], key=lambda item: item["index"])
        if len(data) != len(inputs):
            raise ValueError("embedding provider returned a different number of vectors")
        vectors = [
            EmbeddingVector(id=item.id, vector=[float(value) for value in row["embedding"]])
            for item, row in zip(inputs, data, strict=True)
        ]
        for vector in vectors:
            if len(vector.vector) != self.info.dimensions:
                raise ValueError(
                    f"embedding provider returned {len(vector.vector)} dimensions, "
                    f"expected {self.info.dimensions}"
                )
        return vectors


def get_embedding_provider(settings: Settings | None = None) -> EmbeddingProvider:
    cfg = settings or get_settings()
    if cfg.embedding_provider == "openai":
        return OpenAIEmbeddingProvider(cfg)
    if cfg.embedding_provider == "deterministic":
        return DeterministicEmbeddingProvider(cfg)
    raise ValueError(f"unsupported embedding provider: {cfg.embedding_provider}")
