"""Reranker provider abstraction and deterministic local provider."""

from __future__ import annotations

from typing import Protocol

import httpx

from app.core.config import Settings, get_settings
from app.reranking.models import RerankCandidate, RerankResult
from app.retrieval.bm25 import tokenize


class RerankerProvider(Protocol):
    name: str

    def rerank(self, *, query: str, candidates: list[RerankCandidate]) -> list[RerankResult]:
        """Return reranker scores for candidate chunks."""


class LexicalOverlapReranker:
    name = "lexical_overlap"

    def rerank(self, *, query: str, candidates: list[RerankCandidate]) -> list[RerankResult]:
        query_terms = set(tokenize(query))
        if not query_terms:
            return [RerankResult(chunk_id=item.chunk_id, score=0.0) for item in candidates]
        results: list[RerankResult] = []
        for candidate in candidates:
            candidate_terms = set(tokenize(candidate.text))
            overlap = len(query_terms.intersection(candidate_terms))
            score = overlap / len(query_terms)
            results.append(RerankResult(chunk_id=candidate.chunk_id, score=score))
        return results


class NoOpReranker:
    name = "none"

    def rerank(self, *, query: str, candidates: list[RerankCandidate]) -> list[RerankResult]:
        return [
            RerankResult(chunk_id=item.chunk_id, score=1.0 / item.rank)
            for item in candidates
        ]


class CohereReranker:
    name = "cohere"

    def __init__(self, settings: Settings | None = None) -> None:
        cfg = settings or get_settings()
        if not cfg.cohere_api_key:
            raise ValueError("COHERE_API_KEY is required when RERANKER_PROVIDER=cohere")
        self.settings = cfg

    def rerank(self, *, query: str, candidates: list[RerankCandidate]) -> list[RerankResult]:
        if not candidates:
            return []
        response = httpx.post(
            f"{self.settings.cohere_base_url.rstrip('/')}/v2/rerank",
            headers={
                "Authorization": f"Bearer {self.settings.cohere_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.settings.reranker_model,
                "query": query,
                "documents": [item.text for item in candidates],
                "top_n": len(candidates),
            },
            timeout=self.settings.reranker_timeout_seconds,
        )
        response.raise_for_status()
        by_index = {index: item for index, item in enumerate(candidates)}
        results = []
        for item in response.json()["results"]:
            candidate = by_index[int(item["index"])]
            results.append(
                RerankResult(
                    chunk_id=candidate.chunk_id,
                    score=float(item["relevance_score"]),
                )
            )
        return results


def get_reranker_provider(name: str, settings: Settings | None = None) -> RerankerProvider:
    if name == "cohere":
        return CohereReranker(settings)
    if name == "lexical_overlap":
        return LexicalOverlapReranker()
    if name == "none":
        return NoOpReranker()
    raise ValueError(f"unsupported reranker provider: {name}")
