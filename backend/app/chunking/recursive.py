"""Recursive splitter: sections → paragraphs → sentences → tokens."""

from __future__ import annotations

from app.chunking.fixed import chunk_fixed
from app.chunking.models import ChunkDraft, ChunkKind, ChunkResult, ChunkStrategy
from app.chunking.tokens import count_tokens, split_sentences


def chunk_recursive(
    text: str,
    *,
    chunk_size: int = 256,
    overlap: int = 32,
    page: int | None = None,
    section: str | None = None,
) -> list[ChunkDraft]:
    cleaned = text.strip()
    if not cleaned:
        return []
    if count_tokens(cleaned) <= chunk_size:
        return [
            ChunkDraft(
                text=cleaned,
                token_count=count_tokens(cleaned),
                page=page,
                section=section,
                kind=ChunkKind.LEAF,
                metadata={"split": "whole"},
            )
        ]
    for separator, label in (
        ("\n\n", "paragraph"),
        ("\n", "line"),
    ):
        parts = [part.strip() for part in cleaned.split(separator) if part.strip()]
        if len(parts) > 1:
            return _merge_parts(
                parts,
                chunk_size=chunk_size,
                overlap=overlap,
                page=page,
                section=section,
                split=label,
            )
    sentences = split_sentences(cleaned)
    if len(sentences) > 1:
        return _merge_parts(
            sentences,
            chunk_size=chunk_size,
            overlap=overlap,
            page=page,
            section=section,
            split="sentence",
        )
    return [
        draft
        for draft in chunk_fixed(
            cleaned,
            chunk_size=chunk_size,
            overlap=overlap,
            page=page,
            section=section,
            metadata={"split": "token"},
        )
    ]


def _merge_parts(
    parts: list[str],
    *,
    chunk_size: int,
    overlap: int,
    page: int | None,
    section: str | None,
    split: str,
) -> list[ChunkDraft]:
    drafts: list[ChunkDraft] = []
    buffer: list[str] = []
    buffer_tokens = 0

    def flush() -> None:
        nonlocal buffer, buffer_tokens
        if not buffer:
            return
        body = "\n\n".join(buffer) if split == "paragraph" else " ".join(buffer)
        drafts.append(
            ChunkDraft(
                text=body,
                token_count=count_tokens(body),
                page=page,
                section=section,
                kind=ChunkKind.LEAF,
                metadata={"split": split},
            )
        )
        buffer = []
        buffer_tokens = 0

    for part in parts:
        size = count_tokens(part)
        if size > chunk_size:
            flush()
            drafts.extend(
                chunk_recursive(
                    part,
                    chunk_size=chunk_size,
                    overlap=overlap,
                    page=page,
                    section=section,
                )
            )
            continue
        if buffer_tokens + size > chunk_size and buffer:
            flush()
        buffer.append(part)
        buffer_tokens += size
    flush()
    return drafts


def chunk_recursive_document(
    text: str,
    *,
    chunk_size: int = 256,
    overlap: int = 32,
) -> ChunkResult:
    return ChunkResult(
        strategy=ChunkStrategy.RECURSIVE,
        chunks=chunk_recursive(text, chunk_size=chunk_size, overlap=overlap),
    )
