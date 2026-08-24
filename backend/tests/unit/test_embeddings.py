from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.embeddings.batching import BatchEmbedder, batched
from app.embeddings.models import EmbeddingInput, EmbeddingProviderInfo, EmbeddingVector
from app.embeddings.providers import DeterministicEmbeddingProvider
from app.embeddings.service import chunk_payload, stable_point_id
from app.indexing.qdrant import QdrantIndexer, VectorDimensionMismatch
from app.models.chunk import DocumentChunk
from app.models.document import Document, DocumentVersion


def test_deterministic_provider_returns_stable_normalized_vectors() -> None:
    settings = Settings(embedding_dimension=8, embedding_batch_size=4)
    provider = DeterministicEmbeddingProvider(settings)

    first = provider.embed([EmbeddingInput(id="a", text="hello")])[0]
    second = provider.embed([EmbeddingInput(id="a", text="hello")])[0]

    assert first.vector == second.vector
    assert len(first.vector) == 8
    assert sum(value * value for value in first.vector) == pytest.approx(1.0)


def test_batched_splits_inputs() -> None:
    items = [EmbeddingInput(id=str(index), text="x") for index in range(5)]

    batches = list(batched(items, 2))

    assert [[item.id for item in batch] for batch in batches] == [["0", "1"], ["2", "3"], ["4"]]


@dataclass
class FlakyProvider:
    info: EmbeddingProviderInfo
    calls: int = 0

    def embed(self, inputs: list[EmbeddingInput]) -> list[EmbeddingVector]:
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("temporary")
        return [EmbeddingVector(id=item.id, vector=[1.0, 0.0]) for item in inputs]


def test_batch_embedder_retries_provider_failures() -> None:
    provider = FlakyProvider(
        EmbeddingProviderInfo(
            provider="fake",
            model="fake",
            dimensions=2,
            max_batch_size=2,
            embedding_version=1,
        )
    )
    settings = Settings(
        embedding_batch_size=2,
        embedding_max_retries=2,
        embedding_retry_base_seconds=0,
    )

    vectors = BatchEmbedder(provider, settings).embed([EmbeddingInput(id="a", text="hello")])

    assert provider.calls == 2
    assert vectors == [EmbeddingVector(id="a", vector=[1.0, 0.0])]


def test_stable_point_id_changes_when_model_version_changes() -> None:
    chunk_id = uuid4()

    first = stable_point_id(chunk_id, provider="p", model="m", embedding_version=1)
    second = stable_point_id(chunk_id, provider="p", model="m", embedding_version=1)
    reembedded = stable_point_id(chunk_id, provider="p", model="m", embedding_version=2)

    assert first == second
    assert first != reembedded


class FakeQdrantClient:
    def __init__(self, vector_size: int | None = None) -> None:
        self.vector_size = vector_size
        self.created = False
        self.indexes: list[str] = []

    def collection_exists(self, collection_name: str) -> bool:
        return self.vector_size is not None

    def get_collection(self, collection_name: str):
        return SimpleNamespace(
            config=SimpleNamespace(
                params=SimpleNamespace(vectors=SimpleNamespace(size=self.vector_size))
            )
        )

    def create_collection(self, collection_name: str, vectors_config) -> None:
        self.created = True
        self.vector_size = vectors_config.size

    def create_payload_index(self, collection_name: str, field_name: str, field_schema) -> None:
        self.indexes.append(field_name)


def test_qdrant_indexer_creates_collection_and_payload_indexes() -> None:
    client = FakeQdrantClient()
    indexer = QdrantIndexer(client=client, settings=Settings(qdrant_collection="test_chunks"))

    indexer.ensure_collection(vector_size=16)

    assert client.created
    assert client.vector_size == 16
    assert "organization_id" in client.indexes
    assert "is_current" in client.indexes


def test_qdrant_indexer_rejects_dimension_mismatch() -> None:
    client = FakeQdrantClient(vector_size=8)
    indexer = QdrantIndexer(client=client, settings=Settings(qdrant_collection="test_chunks"))

    with pytest.raises(VectorDimensionMismatch):
        indexer.ensure_collection(vector_size=16)


def test_chunk_payload_contains_retrieval_and_acl_metadata() -> None:
    document = Document(
        id=uuid4(),
        organization_id=uuid4(),
        workspace_id=uuid4(),
        source_connection_id=uuid4(),
        source_type="file_upload",
        source_id="policy.md",
        title="Policy",
        mime_type="text/markdown",
        current_version=1,
        permissions={"allowed_users": ["u1"], "allowed_groups": ["g1"]},
        extra_metadata={"tag": "hr"},
    )
    version = DocumentVersion(
        id=uuid4(),
        document_id=document.id,
        version_number=1,
        content_hash="abc",
        raw_object_key="raw/key",
        size_bytes=10,
        is_current=True,
        retrieved_at=None,
        language="en",
        chunk_strategy="fixed",
        chunker_version=1,
    )
    chunk = DocumentChunk(
        id=uuid4(),
        document_id=document.id,
        version_id=version.id,
        ordinal=0,
        text="hello",
        token_count=1,
        strategy="fixed",
        kind="leaf",
        extra={"heading": "Intro"},
    )

    payload = chunk_payload(
        document=document,
        version=version,
        chunk=chunk,
        provider="deterministic",
        model="deterministic-v1",
        embedding_version=1,
        dimensions=8,
        content_hash="hash",
    )

    assert payload["organization_id"] == str(document.organization_id)
    assert payload["is_current"] is True
    assert payload["allowed_users"] == ["u1"]
    assert payload["allowed_groups"] == ["g1"]
    assert payload["metadata"] == {"tag": "hr", "heading": "Intro"}
