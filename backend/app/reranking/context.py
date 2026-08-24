"""Context selection after retrieval and reranking."""

from __future__ import annotations

from app.retrieval.models import RetrievalHit, SelectedContext


def select_context(hits: list[RetrievalHit], *, token_budget: int) -> list[SelectedContext]:
    if token_budget <= 0:
        return []
    selected: list[SelectedContext] = []
    used = 0
    seen_parent_or_chunk: set[str] = set()
    for hit in hits:
        key = str(hit.metadata.get("parent_chunk_id") or hit.chunk_id)
        if key in seen_parent_or_chunk:
            continue
        token_count = int(hit.metadata.get("token_count") or _estimate_tokens(hit.text))
        if used + token_count > token_budget and selected:
            continue
        selected.append(SelectedContext(hit=hit, token_count=token_count))
        seen_parent_or_chunk.add(key)
        used += token_count
        if used >= token_budget:
            break
    return selected


def _estimate_tokens(text: str) -> int:
    return max(1, len(text.split()))
