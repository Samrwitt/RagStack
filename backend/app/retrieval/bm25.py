"""Indexed sparse retrieval over current document chunks."""

from __future__ import annotations

import re

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.chunk import DocumentChunk
from app.models.document import Document, DocumentVersion
from app.retrieval.acl import can_read_document
from app.retrieval.filters import apply_document_filters
from app.retrieval.models import RetrievalHit, RetrievalRequest

TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")


class PostgresSparseRetriever:
    """Sparse retriever backed by PostgreSQL full-text search and a GIN index."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def search(self, request: RetrievalRequest) -> list[RetrievalHit]:
        if not tokenize(request.query):
            return []
        tsquery = func.plainto_tsquery("simple", request.query)
        score = func.ts_rank_cd(DocumentChunk.search_vector, tsquery).label("sparse_score")
        stmt = (
            select(DocumentChunk, Document, DocumentVersion, score)
            .join(Document, DocumentChunk.document_id == Document.id)
            .join(DocumentVersion, DocumentChunk.version_id == DocumentVersion.id)
            .where(DocumentChunk.search_vector.op("@@")(tsquery))
            .order_by(score.desc(), DocumentChunk.ordinal.asc())
            .limit(request.candidate_k)
        )
        stmt = apply_document_filters(stmt, request.filters)
        rows = self.session.execute(stmt).all()
        hits: list[RetrievalHit] = []
        for chunk, document, version, sparse_score in rows:
            if not can_read_document(document.permissions or {}, request.acl):
                continue
            hits.append(
                self._hit(
                    chunk=chunk,
                    document=document,
                    version=version,
                    score=float(sparse_score),
                    rank=len(hits) + 1,
                )
            )
            if len(hits) >= request.top_k:
                break
        return hits

    def _hit(
        self,
        *,
        chunk: DocumentChunk,
        document: Document,
        version: DocumentVersion,
        score: float,
        rank: int,
    ) -> RetrievalHit:
        return RetrievalHit(
            chunk_id=chunk.id,
            document_id=document.id,
            version_id=version.id,
            score=score,
            rank=rank,
            text=chunk.text,
            title=document.title,
            source_type=document.source_type,
            source_url=document.source_url,
            page=chunk.page,
            section=chunk.section,
            metadata={
                **(document.extra_metadata or {}),
                **(chunk.extra or {}),
                "parent_chunk_id": str(chunk.parent_chunk_id) if chunk.parent_chunk_id else None,
                "token_count": chunk.token_count,
            },
            scores={"sparse": score},
        )


BM25Retriever = PostgresSparseRetriever


def tokenize(text: str) -> list[str]:
    return [match.group(0).lower() for match in TOKEN_RE.finditer(text)]
