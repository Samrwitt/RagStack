"""Reciprocal Rank Fusion."""

from __future__ import annotations

from collections.abc import Iterable
from uuid import UUID

from app.retrieval.models import RetrievalHit


def reciprocal_rank_fusion(
    ranked_lists: Iterable[list[RetrievalHit]],
    *,
    k: int = 60,
    top_k: int = 10,
) -> list[RetrievalHit]:
    fused: dict[UUID, RetrievalHit] = {}
    scores: dict[UUID, float] = {}
    components: dict[UUID, dict[str, float]] = {}
    for ranked in ranked_lists:
        for index, hit in enumerate(ranked, start=1):
            score = 1.0 / (k + index)
            fused.setdefault(hit.chunk_id, hit)
            scores[hit.chunk_id] = scores.get(hit.chunk_id, 0.0) + score
            for name, value in hit.scores.items():
                components.setdefault(hit.chunk_id, {})[name] = value
    ordered = sorted(fused.values(), key=lambda hit: scores[hit.chunk_id], reverse=True)
    return [
        RetrievalHit(
            chunk_id=hit.chunk_id,
            document_id=hit.document_id,
            version_id=hit.version_id,
            score=scores[hit.chunk_id],
            rank=rank,
            text=hit.text,
            title=hit.title,
            source_type=hit.source_type,
            source_url=hit.source_url,
            page=hit.page,
            section=hit.section,
            metadata=hit.metadata,
            scores={**components.get(hit.chunk_id, {}), "rrf": scores[hit.chunk_id]},
        )
        for rank, hit in enumerate(ordered[:top_k], start=1)
    ]
