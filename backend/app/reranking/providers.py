"""Reranker provider abstraction and deterministic local provider."""

from __future__ import annotations

from typing import Protocol

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


def get_reranker_provider(name: str) -> RerankerProvider:
    if name == "lexical_overlap":
        return LexicalOverlapReranker()
    if name == "none":
        return NoOpReranker()
    raise ValueError(f"unsupported reranker provider: {name}")
