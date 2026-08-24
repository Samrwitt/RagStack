"""Citation resolution from selected retrieval hits."""

from __future__ import annotations

from app.generation.models import Citation
from app.retrieval.models import RetrievalHit


def resolve_citations(hits: list[RetrievalHit]) -> list[Citation]:
    citations: list[Citation] = []
    seen: set[tuple] = set()
    for hit in hits:
        key = (hit.document_id, hit.version_id, hit.chunk_id)
        if key in seen:
            continue
        seen.add(key)
        citations.append(
            Citation(
                index=len(citations) + 1,
                document_id=hit.document_id,
                version_id=hit.version_id,
                chunk_id=hit.chunk_id,
                title=hit.title,
                source_type=hit.source_type,
                source_url=hit.source_url,
                page=hit.page,
                section=hit.section,
            )
        )
    return citations
