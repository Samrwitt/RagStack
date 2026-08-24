"""Select and run a chunking strategy."""

from __future__ import annotations

from app.chunking.fixed import chunk_fixed_document
from app.chunking.models import BlockInput, ChunkResult, ChunkStrategy
from app.chunking.parent_child import chunk_parent_child
from app.chunking.recursive import chunk_recursive_document
from app.chunking.structure import chunk_heading_aware


def blocks_to_text(blocks: list[BlockInput]) -> str:
    return "\n\n".join(
        block.text.strip()
        for block in blocks
        if not block.dropped and block.text.strip()
    )


def run_chunker(
    blocks: list[BlockInput],
    *,
    strategy: str | ChunkStrategy = ChunkStrategy.PARENT_CHILD,
    chunk_size: int = 256,
    overlap: int = 32,
    parent_max_tokens: int = 1024,
) -> ChunkResult:
    chosen = ChunkStrategy(strategy)
    text = blocks_to_text(blocks)
    if chosen is ChunkStrategy.FIXED:
        return chunk_fixed_document(text, chunk_size=chunk_size, overlap=overlap)
    if chosen is ChunkStrategy.RECURSIVE:
        return chunk_recursive_document(text, chunk_size=chunk_size, overlap=overlap)
    if chosen is ChunkStrategy.HEADING_AWARE:
        return chunk_heading_aware(blocks, chunk_size=chunk_size, overlap=overlap)
    if chosen is ChunkStrategy.PARENT_CHILD:
        return chunk_parent_child(
            blocks,
            chunk_size=chunk_size,
            overlap=overlap,
            parent_max_tokens=parent_max_tokens,
        )
    raise ValueError(f"unknown chunk strategy {strategy!r}")
