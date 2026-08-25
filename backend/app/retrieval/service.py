"""Retrieval service orchestration."""

from __future__ import annotations

from time import perf_counter
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.observability.metrics import (
    RETRIEVAL_LATENCY_SECONDS,
    RETRIEVAL_ZERO_RESULTS,
    increment,
    observe,
)
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
        self.dense = DenseRetriever(session, settings=self.settings)
        self.reranking = RerankingService(settings=self.settings)

    def search(self, request: RetrievalRequest) -> list[RetrievalHit]:
        started = perf_counter()
        labels = {"mode": request.mode.value}
        try:
            candidates = self._retrieve_candidates(request)
            if request.rerank and self.settings.reranker_enabled:
                hits = self.reranking.rerank(
                    query=request.query,
                    candidates=candidates,
                    top_k=request.top_k,
                )
            else:
                hits = [
                    self._with_rank(hit, rank)
                    for rank, hit in enumerate(candidates[: request.top_k], start=1)
                ]
            if not hits:
                increment(RETRIEVAL_ZERO_RESULTS, labels=labels)
            return hits
        finally:
            observe(RETRIEVAL_LATENCY_SECONDS, perf_counter() - started, labels=labels)

    def search_with_context(
        self,
        request: RetrievalRequest,
    ) -> tuple[list[RetrievalHit], list[SelectedContext]]:
        hits = self.search(request)
        return hits, self.reranking.select_context(
            hits,
            token_budget=request.context_token_budget,
        )

    def search_debug(
        self,
        request: RetrievalRequest,
    ) -> dict[str, Any]:
        candidate_k = request.candidate_k if request.rerank else request.top_k
        dense_req = self._candidate_request(request, RetrievalMode.DENSE, candidate_k)
        sparse_req = self._candidate_request(request, RetrievalMode.SPARSE, candidate_k)

        t0 = perf_counter()
        dense_hits = self.dense.search(dense_req)
        t_dense = (perf_counter() - t0) * 1000

        t0 = perf_counter()
        sparse_hits = self.bm25.search(sparse_req)
        t_sparse = (perf_counter() - t0) * 1000

        t0 = perf_counter()
        rrf_hits = reciprocal_rank_fusion([dense_hits, sparse_hits], top_k=candidate_k)
        t_rrf = (perf_counter() - t0) * 1000

        if request.mode == RetrievalMode.DENSE:
            candidates = dense_hits
        elif request.mode == RetrievalMode.SPARSE:
            candidates = sparse_hits
        else:
            candidates = rrf_hits

        t0 = perf_counter()
        if request.rerank and self.settings.reranker_enabled:
            reranked_hits = self.reranking.rerank(
                query=request.query,
                candidates=candidates,
                top_k=request.top_k,
            )
        else:
            reranked_hits = [
                self._with_rank(hit, rank)
                for rank, hit in enumerate(candidates[: request.top_k], start=1)
            ]
        t_rerank = (perf_counter() - t0) * 1000

        selected = self.reranking.select_context(
            reranked_hits,
            token_budget=request.context_token_budget,
        )
        final_context = [item.hit for item in selected]

        return {
            "query": request.query,
            "mode": request.mode.value,
            "dense_hits": dense_hits,
            "sparse_hits": sparse_hits,
            "rrf_hits": rrf_hits,
            "reranked_hits": reranked_hits,
            "final_context": final_context,
            "latency_ms": {
                "dense": round(t_dense, 2),
                "sparse": round(t_sparse, 2),
                "rrf": round(t_rrf, 2),
                "rerank": round(t_rerank, 2),
                "total": round(t_dense + t_sparse + t_rrf + t_rerank, 2),
            },
        }

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
