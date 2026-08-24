"""DOCX parser. Walks body children so tables stay in reading order."""

from __future__ import annotations

import io

from docx import Document as DocxDocument
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph

from app.ingestion.mime import canonicalize_mime
from app.parsers.blocks import BlockAccumulator, fallback_title
from app.parsers.errors import PermanentParseError
from app.parsers.models import BlockType, ParsedDocument, RawDocument

_DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


class DocxParser:
    name = "docx"
    version = 1

    def supports(self, mime_type: str) -> bool:
        return canonicalize_mime(mime_type) == _DOCX_MIME

    def parse(self, raw_document: RawDocument) -> ParsedDocument:
        try:
            document = DocxDocument(io.BytesIO(raw_document.data))
        except Exception as exc:
            raise PermanentParseError(f"corrupt or unreadable DOCX: {exc}") from exc
        acc = BlockAccumulator(default_title=raw_document.title)
        title = fallback_title(raw_document.filename, raw_document.title)
        list_items: list[str] = []
        list_ordered = False

        def flush_list() -> None:
            nonlocal list_ordered
            if list_items:
                acc.add(
                    BlockType.LIST,
                    "\n".join(list_items),
                    metadata={"ordered": list_ordered, "items": list(list_items)},
                )
                list_items.clear()

        for child in document.element.body:
            if child.tag == qn("w:p"):
                paragraph = Paragraph(child, document)
                text = paragraph.text.strip()
                style = (paragraph.style.name if paragraph.style else "") or ""
                if _is_list(paragraph) and text:
                    flush_heading = style.startswith("Heading") or style.startswith("Title")
                    if flush_heading:
                        flush_list()
                    else:
                        list_ordered = _is_ordered(paragraph)
                        list_items.append(text)
                        continue
                flush_list()
                if not text:
                    continue
                if style.startswith("Title"):
                    acc.add(BlockType.TITLE, text, level=1)
                elif style.startswith("Heading"):
                    level = _heading_level(style)
                    if level == 1 and acc.title is None:
                        acc.add(BlockType.TITLE, text, level=1)
                    else:
                        acc.add(BlockType.HEADING, text, level=level)
                elif style.startswith("Quote") or style.startswith("Intense Quote"):
                    acc.add(BlockType.QUOTE, text)
                else:
                    acc.add(BlockType.PARAGRAPH, text)
            elif child.tag == qn("w:tbl"):
                flush_list()
                table = Table(child, document)
                rows = [[cell.text.strip() for cell in row.cells] for row in table.rows]
                acc.add(BlockType.TABLE, _pipe_table(rows), metadata={"rows": rows})
        flush_list()
        return acc.seal(parser_name=self.name, parser_version=self.version, fallback=title)


def _heading_level(style: str) -> int:
    digits = "".join(ch for ch in style if ch.isdigit())
    if digits:
        return max(1, min(int(digits), 6))
    return 1


def _is_list(paragraph: Paragraph) -> bool:
    numbering = paragraph._p.pPr  # noqa: SLF001
    if numbering is None or numbering.numPr is None:
        return False
    return numbering.numPr.numId is not None


def _is_ordered(paragraph: Paragraph) -> bool:
    style = (paragraph.style.name if paragraph.style else "") or ""
    return "Number" in style or "List Number" in style


def _pipe_table(rows: list[list[str]]) -> str:
    if not rows:
        return ""
    width = max(len(row) for row in rows)
    normalized = [row + [""] * (width - len(row)) for row in rows]
    lines = ["| " + " | ".join(normalized[0]) + " |"]
    if len(normalized) > 1:
        lines.append("| " + " | ".join("---" for _ in range(width)) + " |")
        for row in normalized[1:]:
            lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)
