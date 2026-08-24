"""Embedding and vector indexing orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, selectinload

from app.core.config import Settings, get_settings
from app.embeddings.batching import BatchEmbedder
from app.embeddings.models import (
    EMBEDDING_RECORD_STATUS_EMBEDDED,
    EMBEDDING_RECORD_STATUS_INDEXED,
    EmbeddingInput,
)
from app.embeddings.providers import EmbeddingProvider, get_embedding_provider
from app.indexing.qdrant import QdrantIndexer, VectorPoint
from app.ingestion.errors import NotFoundError
from app.ingestion.hashing import sha256_digest
from app.ingestion.state_machine import transition
from app.models.chunk import DocumentChunk
from app.models.document import Document, DocumentVersion
from app.models.embedding import ChunkEmbedding
from app.models.enums import DocumentState


def _utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class EmbeddingOutcome:
    document_id: UUID
    version_id: UUID
    chunk_count: int
    collection_name: str
    provider: str
    model: str
    dimensions: int


class EmbeddingService:
    def __init__(
        self,
        session: Session,
        *,
        provider: EmbeddingProvider | None = None,
        indexer: QdrantIndexer | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.session = session
        self.settings = settings or get_settings()
        self.provider = provider or get_embedding_provider(self.settings)
        self.indexer = indexer or QdrantIndexer(settings=self.settings)
        self.batch_embedder = BatchEmbedder(self.provider, self.settings)

    def embed_current_document(self, document_id: UUID) -> EmbeddingOutcome:
        document = self._get_document(document_id)
        version = self._current_version(document)
        chunks = self._current_chunks(version)
        info = self.provider.info
        now = _utcnow()

        if not chunks:
            raise NotFoundError("document version has no chunks to embed")

        document.current_state = transition(document.current_state, DocumentState.EMBEDDING).value
        vectors = self.batch_embedder.embed(
            [EmbeddingInput(id=str(chunk.id), text=chunk.text) for chunk in chunks]
        )
        vector_by_id = {item.id: item.vector for item in vectors}

        self.indexer.ensure_collection(vector_size=info.dimensions)
        point_records: list[VectorPoint] = []
        for chunk in chunks:
            point_id = stable_point_id(
                chunk.id,
                provider=info.provider,
                model=info.model,
                embedding_version=info.embedding_version,
            )
            content_hash = sha256_digest(chunk.text.encode("utf-8"))
            self._upsert_embedding_record(
                chunk=chunk,
                document=document,
                version=version,
                point_id=point_id,
                content_hash=content_hash,
                embedded_at=now,
            )
            point_records.append(
                VectorPoint(
                    id=point_id,
                    vector=vector_by_id[str(chunk.id)],
                    payload=chunk_payload(
                        document=document,
                        version=version,
                        chunk=chunk,
                        provider=info.provider,
                        model=info.model,
                        embedding_version=info.embedding_version,
                        dimensions=info.dimensions,
                        content_hash=content_hash,
                    ),
                )
            )

        version.embedding_provider = info.provider
        version.embedding_model = info.model
        version.embedding_version = info.embedding_version
        version.embedding_dimension = info.dimensions
        version.embedded_at = now
        version.qdrant_collection = self.indexer.collection_name
        document.current_state = transition(document.current_state, DocumentState.EMBEDDED).value

        document.current_state = transition(document.current_state, DocumentState.INDEXING).value
        self.indexer.upsert(point_records)
        indexed_at = _utcnow()
        self._mark_records_indexed(version.id, indexed_at)
        version.indexed_at = indexed_at
        document.current_state = transition(document.current_state, DocumentState.INDEXED).value
        document.last_error = None

        return EmbeddingOutcome(
            document_id=document.id,
            version_id=version.id,
            chunk_count=len(chunks),
            collection_name=self.indexer.collection_name,
            provider=info.provider,
            model=info.model,
            dimensions=info.dimensions,
        )

    def _get_document(self, document_id: UUID) -> Document:
        document = self.session.scalars(
            select(Document)
            .options(selectinload(Document.source_connection))
            .where(Document.id == document_id)
        ).first()
        if document is None:
            raise NotFoundError(f"document {document_id} not found")
        return document

    def _current_version(self, document: Document) -> DocumentVersion:
        version = self.session.scalars(
            select(DocumentVersion).where(
                DocumentVersion.document_id == document.id,
                DocumentVersion.is_current.is_(True),
            )
        ).first()
        if version is None:
            raise NotFoundError("document has no current version")
        return version

    def _current_chunks(self, version: DocumentVersion) -> list[DocumentChunk]:
        return list(
            self.session.scalars(
                select(DocumentChunk)
                .where(DocumentChunk.version_id == version.id)
                .order_by(DocumentChunk.ordinal)
            ).all()
        )

    def _upsert_embedding_record(
        self,
        *,
        chunk: DocumentChunk,
        document: Document,
        version: DocumentVersion,
        point_id: str,
        content_hash: str,
        embedded_at: datetime,
    ) -> None:
        info = self.provider.info
        values = {
            "organization_id": document.organization_id,
            "document_id": document.id,
            "version_id": version.id,
            "chunk_id": chunk.id,
            "provider": info.provider,
            "model": info.model,
            "embedding_version": info.embedding_version,
            "dimensions": info.dimensions,
            "content_hash": content_hash,
            "qdrant_collection": self.indexer.collection_name,
            "qdrant_point_id": point_id,
            "status": EMBEDDING_RECORD_STATUS_EMBEDDED,
            "last_error": None,
            "embedded_at": embedded_at,
            "extra": {},
        }
        stmt = insert(ChunkEmbedding).values(**values)
        update_values = {
            key: stmt.excluded[key]
            for key in values
            if key
            not in {
                "organization_id",
                "document_id",
                "version_id",
                "chunk_id",
                "provider",
                "model",
                "embedding_version",
            }
        }
        self.session.execute(
            stmt.on_conflict_do_update(
                constraint="uq_chunk_embedding_provider_model_version",
                set_=update_values,
            )
        )

    def _mark_records_indexed(self, version_id: UUID, indexed_at: datetime) -> None:
        records = self.session.scalars(
            select(ChunkEmbedding).where(
                ChunkEmbedding.version_id == version_id,
                ChunkEmbedding.provider == self.provider.info.provider,
                ChunkEmbedding.model == self.provider.info.model,
                ChunkEmbedding.embedding_version == self.provider.info.embedding_version,
            )
        ).all()
        for record in records:
            record.status = EMBEDDING_RECORD_STATUS_INDEXED
            record.indexed_at = indexed_at


def stable_point_id(
    chunk_id: UUID,
    *,
    provider: str,
    model: str,
    embedding_version: int,
) -> str:
    key = f"corpusforge:{provider}:{model}:{embedding_version}:{chunk_id}"
    return str(uuid5(NAMESPACE_URL, key))


def chunk_payload(
    *,
    document: Document,
    version: DocumentVersion,
    chunk: DocumentChunk,
    provider: str,
    model: str,
    embedding_version: int,
    dimensions: int,
    content_hash: str,
) -> dict:
    permissions = dict(document.permissions or {})
    return {
        "organization_id": str(document.organization_id),
        "workspace_id": str(document.workspace_id),
        "source_connection_id": str(document.source_connection_id),
        "source_type": document.source_type,
        "source_id": document.source_id,
        "source_url": document.source_url,
        "document_id": str(document.id),
        "document_title": document.title,
        "document_version": version.version_number,
        "version_id": str(version.id),
        "is_current": version.is_current,
        "chunk_id": str(chunk.id),
        "parent_chunk_id": str(chunk.parent_chunk_id) if chunk.parent_chunk_id else None,
        "chunk_ordinal": chunk.ordinal,
        "chunk_kind": chunk.kind,
        "page": chunk.page,
        "section": chunk.section,
        "language": version.language or document.language,
        "token_count": chunk.token_count,
        "chunk_strategy": version.chunk_strategy or chunk.strategy,
        "chunker_version": version.chunker_version,
        "parser_name": version.parser_name,
        "parser_version": version.parser_version,
        "embedding_provider": provider,
        "embedding_model": model,
        "embedding_version": embedding_version,
        "embedding_dimension": dimensions,
        "content_hash": content_hash,
        "acl": permissions,
        "allowed_users": permissions.get("allowed_users", []),
        "allowed_groups": permissions.get("allowed_groups", []),
        "metadata": {**(document.extra_metadata or {}), **(chunk.extra or {})},
    }
