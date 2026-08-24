"""Retrieval service orchestration."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.retrieval.bm25 import BM25Retriever
from app.retrieval.models import RetrievalHit, RetrievalMode, RetrievalRequest
from app.retrieval.rrf import reciprocal_rank_fusion


class RetrievalService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.bm25 = BM25Retriever(session)

    def search(self, request: RetrievalRequest) -> list[RetrievalHit]:
        if request.mode == RetrievalMode.SPARSE:
            return self.bm25.search(request)
        if request.mode == RetrievalMode.HYBRID:
            # Dense results plug in here once Phase 7's Qdrant query path lands.
            sparse = self.bm25.search(
                RetrievalRequest(
                    query=request.query,
                    filters=request.filters,
                    acl=request.acl,
                    mode=RetrievalMode.SPARSE,
                    top_k=request.candidate_k,
                    candidate_k=request.candidate_k,
                )
            )
            return reciprocal_rank_fusion([sparse], top_k=request.top_k)
        raise NotImplementedError("dense retrieval is not implemented yet")
