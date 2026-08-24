"""Structure-aware chunking driven by normalized blocks and headings."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.chunking.models import BlockInput, ChunkDraft, ChunkKind, ChunkResult, ChunkStrategy
from app.chunking.recursive import chunk_recursive
from app.chunking.tokens import count_tokens


@dataclass(slots=True)
class _Section:
    title: str | None = None
    level: int = 1
    page: int | None = None
    parts: list[str] = field(default_factory=list)
    block_types: list[str] = field(default_factory=list)


def _active_blocks(blocks: list[BlockInput]) -> list[BlockInput]:
    return [
        block
        for block in blocks
        if not block.dropped and (block.text or "").strip()
    ]


def group_sections(blocks: list[BlockInput]) -> list[_Section]:
    sections: list[_Section] = []
    current = _Section(title=None, level=0, page=None)
    for block in _active_blocks(blocks):
        if block.block_type in {"title", "heading"}:
            if current.parts or current.title:
                sections.append(current)
            current = _Section(
                title=block.text.strip(),
                level=block.heading_level or (1 if block.block_type == "title" else 2),
                page=block.page,
            )
            continue
        current.parts.append(block.text.strip())
        current.block_types.append(block.block_type)
        if current.page is None:
            current.page = block.page
        if current.title is None and block.section:
            current.title = block.section
    if current.parts or current.title:
        sections.append(current)
    return sections


def section_text(section: _Section) -> str:
    pieces: list[str] = []
    if section.title:
        pieces.append(section.title)
    pieces.extend(section.parts)
    return "\n\n".join(piece for piece in pieces if piece)


def chunk_heading_aware(
    blocks: list[BlockInput],
    *,
    chunk_size: int = 256,
    overlap: int = 32,
) -> ChunkResult:
    drafts: list[ChunkDraft] = []
    for section in group_sections(blocks):
        body = section_text(section)
        if not body.strip():
            continue
        section_name = section.title
        if count_tokens(body) <= chunk_size:
            drafts.append(
                ChunkDraft(
                    text=body,
                    token_count=count_tokens(body),
                    page=section.page,
                    section=section_name,
                    kind=ChunkKind.LEAF,
                    metadata={
                        "heading_level": section.level,
                        "block_types": list(section.block_types),
                    },
                )
            )
            continue
        # Keep atomic units (tables/code) as whole chunks when possible.
        atomic = [
            part
            for part, kind in zip(section.parts, section.block_types, strict=False)
            if kind in {"table", "code"}
        ]
        prose_parts = [
            part
            for part, kind in zip(section.parts, section.block_types, strict=False)
            if kind not in {"table", "code"}
        ]
        if section.title:
            prose = "\n\n".join([section.title, *prose_parts]) if prose_parts else section.title
        else:
            prose = "\n\n".join(prose_parts)
        if prose.strip():
            drafts.extend(
                chunk_recursive(
                    prose,
                    chunk_size=chunk_size,
                    overlap=overlap,
                    page=section.page,
                    section=section_name,
                )
            )
        for item in atomic:
            if count_tokens(item) <= chunk_size * 2:
                drafts.append(
                    ChunkDraft(
                        text=item,
                        token_count=count_tokens(item),
                        page=section.page,
                        section=section_name,
                        kind=ChunkKind.LEAF,
                        metadata={"atomic": True},
                    )
                )
            else:
                drafts.extend(
                    chunk_recursive(
                        item,
                        chunk_size=chunk_size,
                        overlap=overlap,
                        page=section.page,
                        section=section_name,
                    )
                )
    return ChunkResult(strategy=ChunkStrategy.HEADING_AWARE, chunks=drafts)
