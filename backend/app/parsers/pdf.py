"""PDF parser: digital text first, structure from fonts/tables, OCR only if needed."""

from __future__ import annotations

import io
from collections import defaultdict
from statistics import median

import pdfplumber

from app.ingestion.mime import canonicalize_mime
from app.parsers.blocks import BlockAccumulator, fallback_title
from app.parsers.errors import PermanentParseError
from app.parsers.models import BlockType, ParsedDocument, RawDocument
from app.parsers.ocr import ocr_pdf_pages, should_ocr


class PdfParser:
    name = "pdf"
    version = 1

    def supports(self, mime_type: str) -> bool:
        return canonicalize_mime(mime_type) == "application/pdf"

    def parse(self, raw_document: RawDocument) -> ParsedDocument:
        try:
            pdf = pdfplumber.open(io.BytesIO(raw_document.data))
        except Exception as exc:
            raise PermanentParseError(f"corrupt or unreadable PDF: {exc}") from exc

        acc = BlockAccumulator(default_title=raw_document.title)
        title = fallback_title(raw_document.filename, raw_document.title)
        used_ocr = False
        try:
            page_count = len(pdf.pages)
            if page_count == 0:
                raise PermanentParseError("PDF has no pages")
            digital_chars = 0
            page_payloads: list[tuple[int, object]] = []
            for index, page in enumerate(pdf.pages, start=1):
                page_payloads.append((index, page))
                digital_chars += len((page.extract_text() or "").strip())

            if should_ocr(digital_chars, page_count):
                ocr_pages, warning = ocr_pdf_pages(raw_document.data)
                if warning:
                    acc.warnings.append(warning)
                if ocr_pages and sum(len(text.strip()) for _, text in ocr_pages) > digital_chars:
                    used_ocr = True
                    for page_number, text in ocr_pages:
                        _ocr_page_blocks(acc, page_number, text)
                elif digital_chars == 0:
                    raise PermanentParseError(
                        "scanned PDF produced no extractable text and OCR did not recover any"
                    )
                else:
                    for page_number, page in page_payloads:
                        _digital_page_blocks(acc, page_number, page)
            else:
                for page_number, page in page_payloads:
                    _digital_page_blocks(acc, page_number, page)
        finally:
            pdf.close()

        parsed = acc.seal(
            parser_name=self.name,
            parser_version=self.version,
            fallback=title,
            used_ocr=used_ocr,
            page_count=page_count,
        )
        return parsed


def _digital_page_blocks(acc: BlockAccumulator, page_number: int, page: object) -> None:
    tables = []
    bboxes: list[tuple[float, float, float, float]] = []
    try:
        found = page.find_tables()  # type: ignore[attr-defined]
    except Exception:
        found = []
    for table in found or []:
        try:
            rows = table.extract() or []
        except Exception:
            rows = []
        cleaned = [[(cell or "").strip() for cell in row] for row in rows]
        if any(any(cell for cell in row) for row in cleaned):
            tables.append(cleaned)
            bboxes.append(table.bbox)
            acc.add(
                BlockType.TABLE,
                _pipe_table(cleaned),
                page=page_number,
                metadata={"rows": cleaned},
            )

    words = []
    try:
        words = page.extract_words(extra_attrs=["size", "fontname"]) or []  # type: ignore[attr-defined]
    except Exception:
        words = []
    words = [word for word in words if not _inside_any(word, bboxes)]
    if words:
        _words_to_blocks(acc, page_number, words)
        return
    text = ""
    try:
        text = page.extract_text() or ""  # type: ignore[attr-defined]
    except Exception:
        text = ""
    _ocr_page_blocks(acc, page_number, text)


def _ocr_page_blocks(acc: BlockAccumulator, page_number: int, text: str) -> None:
    paragraphs = [part.strip() for part in text.replace("\r\n", "\n").split("\n\n")]
    for part in paragraphs:
        lines = [line.strip() for line in part.split("\n") if line.strip()]
        if not lines:
            continue
        if len(lines) == 1 and len(lines[0]) < 80:
            acc.add(BlockType.HEADING, lines[0], level=2, page=page_number)
        else:
            acc.add(BlockType.PARAGRAPH, " ".join(lines), page=page_number)


def _words_to_blocks(acc: BlockAccumulator, page_number: int, words: list[dict]) -> None:
    lines: dict[int, list[dict]] = defaultdict(list)
    for word in words:
        key = int(round(float(word["top"]) / 3.0))
        lines[key].append(word)
    ordered_keys = sorted(lines)
    sizes: list[float] = []
    rendered: list[tuple[str, float]] = []
    for key in ordered_keys:
        row = sorted(lines[key], key=lambda item: float(item["x0"]))
        text = " ".join(item["text"] for item in row).strip()
        if not text:
            continue
        size = max(float(item.get("size") or 0) for item in row)
        rendered.append((text, size))
        sizes.append(size)
    if not rendered:
        return
    typical = median(sizes) if sizes else 0
    unique_sizes = sorted({round(size, 1) for _, size in rendered}, reverse=True)
    for text, size in rendered:
        if typical and size >= typical * 1.25 and len(text) < 120:
            rank = unique_sizes.index(round(size, 1)) if unique_sizes else 0
            level = min(rank + 1, 6)
            if level == 1 and acc.title is None:
                acc.add(BlockType.TITLE, text, level=1, page=page_number)
            else:
                acc.add(BlockType.HEADING, text, level=level, page=page_number)
        else:
            acc.add(BlockType.PARAGRAPH, text, page=page_number)


def _inside_any(word: dict, bboxes: list[tuple[float, float, float, float]]) -> bool:
    x = float(word.get("x0") or 0)
    y = float(word.get("top") or 0)
    return any(x0 <= x <= x1 and top <= y <= bottom for x0, top, x1, bottom in bboxes)


def _pipe_table(rows: list[list[str]]) -> str:
    if not rows:
        return ""
    width = max(len(row) for row in rows) if rows else 0
    normalized = [row + [""] * (width - len(row)) for row in rows]
    lines = ["| " + " | ".join(normalized[0]) + " |"]
    if len(normalized) > 1:
        lines.append("| " + " | ".join("---" for _ in range(width)) + " |")
        for row in normalized[1:]:
            lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)
