"""Fixed-size sliding window over whitespace tokens."""

from __future__ import annotations

from app.chunking.models import ChunkDraft, ChunkKind, ChunkResult, ChunkStrategy
from app.chunking.tokens import count_tokens, join_tokens, tokenize


def chunk_fixed(
    text: str,
    *,
    chunk_size: int = 256,
    overlap: int = 32,
    page: int | None = None,
    section: str | None = None,
    metadata: dict | None = None,
) -> list[ChunkDraft]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be >= 0 and < chunk_size")
    tokens = tokenize(text)
    if not tokens:
        return []
    step = chunk_size - overlap
    drafts: list[ChunkDraft] = []
    start = 0
    while start < len(tokens):
        window = tokens[start : start + chunk_size]
        body = join_tokens(window)
        drafts.append(
            ChunkDraft(
                text=body,
                token_count=count_tokens(body),
                page=page,
                section=section,
                kind=ChunkKind.LEAF,
                metadata={**(metadata or {}), "window_start": start},
            )
        )
        if start + chunk_size >= len(tokens):
            break
        start += step
    return drafts


def chunk_fixed_document(
    text: str,
    *,
    chunk_size: int = 256,
    overlap: int = 32,
) -> ChunkResult:
    return ChunkResult(
        strategy=ChunkStrategy.FIXED,
        chunks=chunk_fixed(text, chunk_size=chunk_size, overlap=overlap),
    )
