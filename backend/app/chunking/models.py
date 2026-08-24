"""Chunk drafts produced by strategies before ORM persistence."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class ChunkStrategy(StrEnum):
    FIXED = "fixed"
    RECURSIVE = "recursive"
    HEADING_AWARE = "heading_aware"
    PARENT_CHILD = "parent_child"


class ChunkKind(StrEnum):
    LEAF = "leaf"
    PARENT = "parent"
    CHILD = "child"


CHUNKER_VERSION = 1


@dataclass(slots=True)
class BlockInput:
    ordinal: int
    block_type: str
    text: str
    page: int | None = None
    heading_level: int | None = None
    section: str | None = None
    dropped: bool = False


@dataclass(slots=True)
class ChunkDraft:
    text: str
    token_count: int
    page: int | None = None
    section: str | None = None
    kind: ChunkKind = ChunkKind.LEAF
    parent_index: int | None = None
    metadata: dict = field(default_factory=dict)


@dataclass(slots=True)
class ChunkResult:
    strategy: ChunkStrategy
    chunks: list[ChunkDraft]
    chunker_version: int = CHUNKER_VERSION
