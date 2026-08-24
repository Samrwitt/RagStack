"""Parent section chunks with child retrieval chunks underneath."""

from __future__ import annotations

from app.chunking.models import (
    BlockInput,
    ChunkDraft,
    ChunkKind,
    ChunkResult,
    ChunkStrategy,
)
from app.chunking.recursive import chunk_recursive
from app.chunking.structure import group_sections, section_text
from app.chunking.tokens import count_tokens, join_tokens, tokenize


def chunk_parent_child(
    blocks: list[BlockInput],
    *,
    chunk_size: int = 256,
    overlap: int = 32,
    parent_max_tokens: int = 1024,
) -> ChunkResult:
    drafts: list[ChunkDraft] = []
    for section in group_sections(blocks):
        body = section_text(section)
        if not body.strip():
            continue
        parent_text = _truncate(body, parent_max_tokens)
        parent_index = len(drafts)
        drafts.append(
            ChunkDraft(
                text=parent_text,
                token_count=count_tokens(parent_text),
                page=section.page,
                section=section.title,
                kind=ChunkKind.PARENT,
                parent_index=None,
                metadata={
                    "heading_level": section.level,
                    "role": "parent",
                },
            )
        )
        children = chunk_recursive(
            body,
            chunk_size=chunk_size,
            overlap=overlap,
            page=section.page,
            section=section.title,
        )
        if len(children) == 1 and children[0].text == parent_text:
            # Single child identical to parent — keep parent only as leaf-like parent.
            drafts[parent_index].kind = ChunkKind.PARENT
            drafts[parent_index].metadata["sole_section"] = True
            continue
        for child in children:
            child.kind = ChunkKind.CHILD
            child.parent_index = parent_index
            child.metadata = {**child.metadata, "role": "child"}
            drafts.append(child)
    return ChunkResult(strategy=ChunkStrategy.PARENT_CHILD, chunks=drafts)


def _truncate(text: str, max_tokens: int) -> str:
    tokens = tokenize(text)
    if len(tokens) <= max_tokens:
        return text
    return join_tokens(tokens[:max_tokens])
