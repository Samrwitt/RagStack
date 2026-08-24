"""Retrieval service orchestration."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.reranking.service import RerankingService
from app.retrieval.bm25 import BM25Retriever
from app.retrieval.dense import DenseRetriever
from app.retrieval.models import RetrievalHit, RetrievalMode, RetrievalRequest, SelectedContext
from app.retrieval.rrf import reciprocal_rank_fusion


class RetrievalService:
    def __init__(self, session: Session, *, settings: Settings | None = None) -> None:
        self.session = session
        self.settings = settings or get_settings()
        self.bm25 = BM25Retriever(session)
        self.dense = DenseRetriever(session)
        self.reranking = RerankingService(settings=self.settings)

    def search(self, request: RetrievalRequest) -> list[RetrievalHit]:
        candidates = self._retrieve_candidates(request)
        if request.rerank:
            return self.reranking.rerank(
                query=request.query,
                candidates=candidates,
                top_k=request.top_k,
            )
        return [
            self._with_rank(hit, rank)
            for rank, hit in enumerate(candidates[: request.top_k], start=1)
        ]

    def search_with_context(
        self,
        request: RetrievalRequest,
    ) -> tuple[list[RetrievalHit], list[SelectedContext]]:
        hits = self.search(request)
        return hits, self.reranking.select_context(
            hits,
            token_budget=request.context_token_budget,
        )

    def _retrieve_candidates(self, request: RetrievalRequest) -> list[RetrievalHit]:
        candidate_k = request.candidate_k if request.rerank else request.top_k
        if request.mode == RetrievalMode.DENSE:
            return self.dense.search(
                self._candidate_request(request, RetrievalMode.DENSE, candidate_k)
            )
        if request.mode == RetrievalMode.SPARSE:
            return self.bm25.search(
                self._candidate_request(request, RetrievalMode.SPARSE, candidate_k)
            )
        if request.mode == RetrievalMode.HYBRID:
            sparse = self.bm25.search(
                self._candidate_request(request, RetrievalMode.SPARSE, candidate_k)
            )
            dense = self.dense.search(
                self._candidate_request(request, RetrievalMode.DENSE, candidate_k)
            )
            return reciprocal_rank_fusion([dense, sparse], top_k=candidate_k)
        raise ValueError(f"unsupported retrieval mode: {request.mode}")

    def _candidate_request(
        self,
        request: RetrievalRequest,
        mode: RetrievalMode,
        candidate_k: int,
    ) -> RetrievalRequest:
        return RetrievalRequest(
            query=request.query,
            filters=request.filters,
            acl=request.acl,
            mode=mode,
            top_k=candidate_k,
            candidate_k=candidate_k,
            rerank=False,
            context_token_budget=request.context_token_budget,
        )

    def _with_rank(self, hit: RetrievalHit, rank: int) -> RetrievalHit:
        return RetrievalHit(
            chunk_id=hit.chunk_id,
            document_id=hit.document_id,
            version_id=hit.version_id,
            score=hit.score,
            rank=rank,
            text=hit.text,
            title=hit.title,
            source_type=hit.source_type,
            source_url=hit.source_url,
            page=hit.page,
            section=hit.section,
            metadata=hit.metadata,
            scores=hit.scores,
        )
