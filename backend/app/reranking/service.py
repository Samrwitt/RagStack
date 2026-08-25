"""Reranking orchestration for retrieval candidates."""

from __future__ import annotations

from app.core.config import Settings, get_settings
from app.reranking.context import select_context
from app.reranking.models import RerankCandidate
from app.reranking.providers import RerankerProvider, get_reranker_provider
from app.retrieval.models import RetrievalHit, SelectedContext


class RerankingService:
    def __init__(
        self,
        *,
        provider: RerankerProvider | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.provider = provider or get_reranker_provider(
            self.settings.reranker_provider,
            self.settings,
        )

    def rerank(
        self,
        *,
        query: str,
        candidates: list[RetrievalHit],
        top_k: int,
    ) -> list[RetrievalHit]:
        if not candidates:
            return []
        inputs = [
            RerankCandidate(
                chunk_id=item.chunk_id,
                text=item.text,
                rank=item.rank,
                score=item.score,
            )
            for item in candidates
        ]
        scores = {
            item.chunk_id: item.score
            for item in self.provider.rerank(query=query, candidates=inputs)
        }
        ordered = sorted(
            candidates,
            key=lambda item: (scores.get(item.chunk_id, 0.0), item.score),
            reverse=True,
        )
        return [
            RetrievalHit(
                chunk_id=hit.chunk_id,
                document_id=hit.document_id,
                version_id=hit.version_id,
                score=scores.get(hit.chunk_id, 0.0),
                rank=rank,
                text=hit.text,
                title=hit.title,
                source_type=hit.source_type,
                source_url=hit.source_url,
                page=hit.page,
                section=hit.section,
                metadata=hit.metadata,
                scores={**hit.scores, "reranker": scores.get(hit.chunk_id, 0.0)},
            )
            for rank, hit in enumerate(ordered[:top_k], start=1)
        ]

    def select_context(
        self,
        hits: list[RetrievalHit],
        *,
        token_budget: int | None = None,
    ) -> list[SelectedContext]:
        return select_context(
            hits,
            token_budget=token_budget or self.settings.context_token_budget,
        )
