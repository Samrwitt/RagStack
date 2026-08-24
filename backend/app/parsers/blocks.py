"""Shared accumulator that tracks heading/section for later citations."""

from __future__ import annotations

from pathlib import Path

from app.parsers.models import Block, BlockType, ParsedDocument


def fallback_title(filename: str | None, explicit: str | None) -> str:
    if explicit:
        return explicit.strip()[:512]
    if filename:
        stem = Path(filename).stem.strip()
        if stem:
            return stem[:512]
    return "Untitled"


class BlockAccumulator:
    def __init__(self, *, default_title: str | None = None) -> None:
        self.blocks: list[Block] = []
        self.title: str | None = None
        self._section: str | None = None
        self.warnings: list[str] = []
        self._fallback = (default_title or "").strip() or None

    def add(
        self,
        block_type: BlockType,
        text: str,
        *,
        level: int | None = None,
        page: int | None = None,
        metadata: dict | None = None,
    ) -> None:
        cleaned = _clean(block_type, text)
        if not cleaned:
            return
        if block_type is BlockType.TITLE and not self.title:
            self.title = cleaned[:512]
        if block_type in {BlockType.TITLE, BlockType.HEADING}:
            self._section = cleaned
        self.blocks.append(
            Block(
                type=block_type,
                text=cleaned,
                level=level,
                page=page,
                section=self._section,
                ordinal=len(self.blocks),
                metadata=metadata or {},
            )
        )

    def seal(
        self,
        *,
        parser_name: str,
        parser_version: int,
        fallback: str,
        used_ocr: bool = False,
        page_count: int | None = None,
    ) -> ParsedDocument:
        title = (self.title or self._fallback or fallback).strip()[:512] or "Untitled"
        blocks = list(self.blocks)
        if not any(block.type is BlockType.TITLE for block in blocks):
            title_block = Block(
                type=BlockType.TITLE,
                text=title,
                section=title,
                ordinal=0,
                metadata={},
            )
            for index, block in enumerate(blocks, start=1):
                block.ordinal = index
                if block.section is None:
                    block.section = title
            blocks.insert(0, title_block)
        else:
            for index, block in enumerate(blocks):
                block.ordinal = index
                if block.section is None:
                    block.section = title
        return ParsedDocument(
            parser_name=parser_name,
            parser_version=parser_version,
            title=title,
            blocks=blocks,
            used_ocr=used_ocr,
            warnings=list(self.warnings),
            page_count=page_count,
        )


def _clean(block_type: BlockType, text: str) -> str:
    if block_type is BlockType.CODE:
        normalized = text.replace("\r\n", "\n").replace("\r", "\n")
        return normalized if normalized.strip() else ""
    if block_type in {BlockType.LIST, BlockType.TABLE}:
        return text.replace("\r\n", "\n").replace("\r", "\n").strip()
    collapsed = " ".join(text.replace("\r\n", "\n").replace("\r", "\n").split())
    return collapsed
