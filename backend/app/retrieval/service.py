"""Retrieval service orchestration."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.retrieval.bm25 import BM25Retriever
from app.retrieval.dense import DenseRetriever
from app.retrieval.models import RetrievalHit, RetrievalMode, RetrievalRequest
from app.retrieval.rrf import reciprocal_rank_fusion


class RetrievalService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.bm25 = BM25Retriever(session)
        self.dense = DenseRetriever(session)

    def search(self, request: RetrievalRequest) -> list[RetrievalHit]:
        if request.mode == RetrievalMode.DENSE:
            return self.dense.search(request)
        if request.mode == RetrievalMode.SPARSE:
            return self.bm25.search(request)
        if request.mode == RetrievalMode.HYBRID:
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
            dense = self.dense.search(
                RetrievalRequest(
                    query=request.query,
                    filters=request.filters,
                    acl=request.acl,
                    mode=RetrievalMode.DENSE,
                    top_k=request.candidate_k,
                    candidate_k=request.candidate_k,
                )
            )
            return reciprocal_rank_fusion([dense, sparse], top_k=request.top_k)
        raise ValueError(f"unsupported retrieval mode: {request.mode}")
