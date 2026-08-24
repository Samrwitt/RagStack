"""Structured parse output — blocks, not a flattened string."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class BlockType(StrEnum):
    TITLE = "title"
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    LIST = "list"
    CODE = "code"
    TABLE = "table"
    QUOTE = "quote"
    IMAGE_CAPTION = "image_caption"


@dataclass(slots=True)
class RawDocument:
    data: bytes
    mime_type: str
    filename: str | None = None
    title: str | None = None


@dataclass(slots=True)
class Block:
    type: BlockType
    text: str
    level: int | None = None
    page: int | None = None
    section: str | None = None
    ordinal: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_record(self) -> dict[str, Any]:
        return {
            "type": self.type.value,
            "text": self.text,
            "level": self.level,
            "page": self.page,
            "section": self.section,
            "ordinal": self.ordinal,
            "metadata": self.metadata,
        }


@dataclass(slots=True)
class ParsedDocument:
    parser_name: str
    parser_version: int
    title: str | None
    blocks: list[Block]
    used_ocr: bool = False
    warnings: list[str] = field(default_factory=list)
    page_count: int | None = None
