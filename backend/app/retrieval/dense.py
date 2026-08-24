"""Dense retrieval against Qdrant, hydrated through PostgreSQL."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.embeddings.models import EmbeddingInput
from app.embeddings.providers import EmbeddingProvider, get_embedding_provider
from app.indexing.qdrant import QdrantIndexer
from app.models.chunk import DocumentChunk
from app.models.document import Document, DocumentVersion
from app.retrieval.acl import can_read_document
from app.retrieval.filters import apply_document_filters
from app.retrieval.models import RetrievalHit, RetrievalRequest
from app.retrieval.qdrant_filters import qdrant_filter


class DenseRetriever:
    def __init__(
        self,
        session: Session,
        *,
        provider: EmbeddingProvider | None = None,
        indexer: QdrantIndexer | None = None,
    ) -> None:
        self.session = session
        self.provider = provider or get_embedding_provider()
        self.indexer = indexer or QdrantIndexer()

    def search(self, request: RetrievalRequest) -> list[RetrievalHit]:
        query_vector = self.provider.embed([EmbeddingInput(id="query", text=request.query)])[0]
        results = self.indexer.search(
            vector=query_vector.vector,
            query_filter=qdrant_filter(request.filters, request.acl),
            limit=request.candidate_k,
        )
        scored_chunk_ids: list[UUID] = []
        score_by_chunk_id: dict[UUID, float] = {}
        for result in results:
            raw_chunk_id = result.payload.get("chunk_id")
            if not raw_chunk_id:
                continue
            chunk_id = UUID(str(raw_chunk_id))
            scored_chunk_ids.append(chunk_id)
            score_by_chunk_id[chunk_id] = result.score
        if not scored_chunk_ids:
            return []

        rows = self._load_rows(scored_chunk_ids, request)
        row_by_chunk_id = {
            chunk.id: (chunk, document, version)
            for chunk, document, version in rows
        }
        hits: list[RetrievalHit] = []
        for chunk_id in scored_chunk_ids:
            row = row_by_chunk_id.get(chunk_id)
            if row is None:
                continue
            chunk, document, version = row
            if not can_read_document(document.permissions or {}, request.acl):
                continue
            score = score_by_chunk_id[chunk_id]
            hits.append(
                RetrievalHit(
                    chunk_id=chunk.id,
                    document_id=document.id,
                    version_id=version.id,
                    score=score,
                    rank=len(hits) + 1,
                    text=chunk.text,
                    title=document.title,
                    source_type=document.source_type,
                    source_url=document.source_url,
                    page=chunk.page,
                    section=chunk.section,
                    metadata={**(document.extra_metadata or {}), **(chunk.extra or {})},
                    scores={"dense": score},
                )
            )
            if len(hits) >= request.top_k:
                break
        return hits

    def _load_rows(
        self,
        chunk_ids: list[UUID],
        request: RetrievalRequest,
    ) -> list[tuple[DocumentChunk, Document, DocumentVersion]]:
        stmt = (
            select(DocumentChunk, Document, DocumentVersion)
            .join(Document, DocumentChunk.document_id == Document.id)
            .join(DocumentVersion, DocumentChunk.version_id == DocumentVersion.id)
            .where(DocumentChunk.id.in_(chunk_ids))
        )
        stmt = apply_document_filters(stmt, request.filters)
        return list(self.session.execute(stmt).all())
