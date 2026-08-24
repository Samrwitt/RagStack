"""Normalized block snapshots used before ORM persistence."""

from __future__ import annotations

from dataclasses import dataclass, field


NORMALIZER_NAME = "default"
NORMALIZER_VERSION = 1


@dataclass(slots=True)
class BlockSnapshot:
    ordinal: int
    block_type: str
    text: str
    page: int | None = None
    heading_level: int | None = None
    section: str | None = None
    extra: dict = field(default_factory=dict)
    normalized_text: str | None = None
    dropped: bool = False
    drop_reason: str | None = None


@dataclass(slots=True)
class NormalizedDocument:
    blocks: list[BlockSnapshot]
    language: str
    content_hash: str
    simhash: int
    kept: int
    dropped: int
    warnings: list[str] = field(default_factory=list)
    normalizer_name: str = NORMALIZER_NAME
    normalizer_version: int = NORMALIZER_VERSION
