"""Plain-text parser: headings, lists, quotes, fenced/indented code, paragraphs."""

from __future__ import annotations

import re

from app.ingestion.mime import canonicalize_mime
from app.parsers.blocks import BlockAccumulator, fallback_title
from app.parsers.models import BlockType, ParsedDocument, RawDocument
from app.parsers.text import decode_bytes

_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
_UL = re.compile(r"^(\s*)[-*+]\s+(.*)$")
_OL = re.compile(r"^(\s*)\d+[.)]\s+(.*)$")
_QUOTE = re.compile(r"^>\s?(.*)$")
_FENCE = re.compile(r"^```(\S*)\s*$")


class TxtParser:
    name = "txt"
    version = 1

    def supports(self, mime_type: str) -> bool:
        return canonicalize_mime(mime_type) == "text/plain"

    def parse(self, raw_document: RawDocument) -> ParsedDocument:
        text = decode_bytes(raw_document.data)
        acc = BlockAccumulator(default_title=raw_document.title)
        title = fallback_title(raw_document.filename, raw_document.title)
        lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        _walk_lines(acc, lines)
        return acc.seal(parser_name=self.name, parser_version=self.version, fallback=title)


def _walk_lines(acc: BlockAccumulator, lines: list[str]) -> None:
    i = 0
    paragraph: list[str] = []
    list_items: list[str] = []
    list_ordered: bool | None = None

    def flush_paragraph() -> None:
        if paragraph:
            acc.add(BlockType.PARAGRAPH, " ".join(paragraph))
            paragraph.clear()

    def flush_list() -> None:
        nonlocal list_ordered
        if list_items:
            acc.add(
                BlockType.LIST,
                "\n".join(list_items),
                metadata={"ordered": bool(list_ordered), "items": list(list_items)},
            )
            list_items.clear()
            list_ordered = None

    while i < len(lines):
        line = lines[i]
        fence = _FENCE.match(line.strip()) if line.strip().startswith("```") else None
        if fence:
            flush_paragraph()
            flush_list()
            language = fence.group(1)
            i += 1
            body: list[str] = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                body.append(lines[i])
                i += 1
            acc.add(BlockType.CODE, "\n".join(body), metadata={"language": language})
            i += 1
            continue

        if line.startswith("    ") and line.strip():
            flush_paragraph()
            flush_list()
            body = []
            while i < len(lines) and (lines[i].startswith("    ") or lines[i] == ""):
                if lines[i] == "" and (i + 1 >= len(lines) or not lines[i + 1].startswith("    ")):
                    break
                body.append(lines[i][4:] if lines[i].startswith("    ") else "")
                i += 1
            acc.add(BlockType.CODE, "\n".join(body), metadata={"language": ""})
            continue

        stripped = line.strip()
        if not stripped:
            flush_paragraph()
            flush_list()
            i += 1
            continue

        heading = _HEADING.match(stripped)
        if heading:
            flush_paragraph()
            flush_list()
            level = len(heading.group(1))
            text = heading.group(2)
            if level == 1 and acc.title is None:
                acc.add(BlockType.TITLE, text, level=1)
            else:
                acc.add(BlockType.HEADING, text, level=level)
            i += 1
            continue

        quote = _QUOTE.match(stripped)
        if quote:
            flush_paragraph()
            flush_list()
            quoted: list[str] = []
            while i < len(lines):
                match = _QUOTE.match(lines[i].strip())
                if not match:
                    break
                quoted.append(match.group(1))
                i += 1
            acc.add(BlockType.QUOTE, " ".join(quoted))
            continue

        ul = _UL.match(line)
        ol = _OL.match(line)
        if ul or ol:
            flush_paragraph()
            ordered = ol is not None
            if list_ordered is not None and ordered != list_ordered:
                flush_list()
            list_ordered = ordered
            item = (ol or ul).group(2)  # type: ignore[union-attr]
            list_items.append(item)
            i += 1
            continue

        flush_list()
        paragraph.append(stripped)
        i += 1

    flush_paragraph()
    flush_list()
