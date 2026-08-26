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


class GeminiEmbeddingProvider:
    """Embedding provider backed by Google Gemini gemini-embedding-001."""

    def __init__(self, settings: Settings | None = None) -> None:
        cfg = settings or get_settings()
        api_key = cfg.gemini_api_key or cfg.openai_api_key
        if not api_key:
            raise ValueError("GEMINI_API_KEY is required when EMBEDDING_PROVIDER=gemini")
        self.settings = cfg
        self.api_key = api_key
        model_name = cfg.embedding_model if cfg.embedding_model and cfg.embedding_model != "text-embedding-3-small" else "gemini-embedding-001"
        self.info = EmbeddingProviderInfo(
            provider="gemini",
            model=model_name,
            dimensions=3072,
            max_batch_size=8,
            embedding_version=cfg.embedding_version,
        )

    def embed(self, inputs: list[EmbeddingInput]) -> list[EmbeddingVector]:
        if not inputs:
            return []
        model = self.info.model
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:batchEmbedContents"
        
        requests_payload = [
            {
                "model": f"models/{model}",
                "content": {"parts": [{"text": item.text}]},
            }
            for item in inputs
        ]
        
        response = httpx.post(
            url,
            params={"key": self.api_key},
            headers={"Content-Type": "application/json"},
            json={"requests": requests_payload},
            timeout=self.settings.openai_timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        embeddings_data = payload.get("embeddings", [])
        if len(embeddings_data) != len(inputs):
            raise ValueError("Gemini embedding provider returned different number of vectors")
        
        vectors = []
        for item, data in zip(inputs, embeddings_data, strict=True):
            vec = [float(v) for v in data.get("values", [])]
            vectors.append(EmbeddingVector(id=item.id, vector=vec))
        return vectors


def get_embedding_provider(settings: Settings | None = None) -> EmbeddingProvider:
    cfg = settings or get_settings()
    provider = cfg.embedding_provider
    if (provider == "deterministic" or not provider) and (cfg.gemini_api_key or cfg.openai_api_key):
        if cfg.gemini_api_key:
            provider = "gemini"
        elif cfg.openai_api_key:
            provider = "openai"

    if provider == "gemini":
        return GeminiEmbeddingProvider(cfg)
    if provider == "openai":
        return OpenAIEmbeddingProvider(cfg)
    if provider == "deterministic":
        return DeterministicEmbeddingProvider(cfg)
    raise ValueError(f"unsupported embedding provider: {cfg.embedding_provider}")
