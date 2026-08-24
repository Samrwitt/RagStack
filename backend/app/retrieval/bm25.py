"""BM25 lexical retrieval over current document chunks."""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.chunk import DocumentChunk
from app.models.document import Document, DocumentVersion
from app.retrieval.acl import can_read_document
from app.retrieval.filters import apply_document_filters
from app.retrieval.models import RetrievalHit, RetrievalRequest

TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")


@dataclass(frozen=True, slots=True)
class _Candidate:
    chunk: DocumentChunk
    document: Document
    version: DocumentVersion
    terms: Counter[str]
    length: int


class BM25Retriever:
    def __init__(self, session: Session, *, k1: float = 1.5, b: float = 0.75) -> None:
        self.session = session
        self.k1 = k1
        self.b = b

    def search(self, request: RetrievalRequest) -> list[RetrievalHit]:
        query_terms = tokenize(request.query)
        if not query_terms:
            return []
        candidates = self._load_candidates(request)
        if not candidates:
            return []
        doc_freq = Counter[str]()
        for candidate in candidates:
            for term in set(candidate.terms):
                doc_freq[term] += 1
        avg_len = sum(candidate.length for candidate in candidates) / len(candidates)
        scored = [
            (self._score(candidate, query_terms, doc_freq, len(candidates), avg_len), candidate)
            for candidate in candidates
        ]
        ranked = [(score, candidate) for score, candidate in scored if score > 0]
        ranked.sort(key=lambda item: item[0], reverse=True)
        return [
            self._hit(candidate, score=score, rank=rank)
            for rank, (score, candidate) in enumerate(ranked[: request.top_k], start=1)
        ]

    def _load_candidates(self, request: RetrievalRequest) -> list[_Candidate]:
        stmt = (
            select(DocumentChunk, Document, DocumentVersion)
            .join(Document, DocumentChunk.document_id == Document.id)
            .join(DocumentVersion, DocumentChunk.version_id == DocumentVersion.id)
        )
        stmt = apply_document_filters(stmt, request.filters)
        rows = self.session.execute(stmt).all()
        candidates: list[_Candidate] = []
        for chunk, document, version in rows:
            if not can_read_document(document.permissions or {}, request.acl):
                continue
            terms = Counter(tokenize(chunk.text))
            if not terms:
                continue
            candidates.append(
                _Candidate(
                    chunk=chunk,
                    document=document,
                    version=version,
                    terms=terms,
                    length=sum(terms.values()),
                )
            )
        return candidates

    def _score(
        self,
        candidate: _Candidate,
        query_terms: list[str],
        doc_freq: Counter[str],
        total_docs: int,
        avg_len: float,
    ) -> float:
        score = 0.0
        for term in query_terms:
            freq = candidate.terms.get(term, 0)
            if freq == 0:
                continue
            idf = math.log(1 + (total_docs - doc_freq[term] + 0.5) / (doc_freq[term] + 0.5))
            denom = freq + self.k1 * (1 - self.b + self.b * candidate.length / avg_len)
            score += idf * (freq * (self.k1 + 1) / denom)
        return score

    def _hit(self, candidate: _Candidate, *, score: float, rank: int) -> RetrievalHit:
        chunk = candidate.chunk
        document = candidate.document
        version = candidate.version
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
            metadata={**(document.extra_metadata or {}), **(chunk.extra or {})},
            scores={"bm25": score},
        )


def tokenize(text: str) -> list[str]:
    return [match.group(0).lower() for match in TOKEN_RE.finditer(text)]
