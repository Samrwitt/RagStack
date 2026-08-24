"""MIME → parser registry. First matching parser wins."""

from __future__ import annotations

from app.ingestion.mime import canonicalize_mime
from app.parsers.errors import UnsupportedMimeError
from app.parsers.html import HtmlParser
from app.parsers.markdown import MarkdownParser
from app.parsers.models import ParsedDocument, RawDocument
from app.parsers.protocol import DocumentParser
from app.parsers.txt import TxtParser


def default_parsers() -> list[DocumentParser]:
    from app.parsers.docx import DocxParser
    from app.parsers.pdf import PdfParser

    return [TxtParser(), MarkdownParser(), HtmlParser(), DocxParser(), PdfParser()]


class ParserRegistry:
    def __init__(self, parsers: list[DocumentParser] | None = None) -> None:
        self._parsers = parsers if parsers is not None else default_parsers()

    def select(self, mime_type: str) -> DocumentParser:
        mime = canonicalize_mime(mime_type) or mime_type
        for parser in self._parsers:
            if parser.supports(mime):
                return parser
        raise UnsupportedMimeError(mime)

    def parse(self, raw_document: RawDocument) -> ParsedDocument:
        parser = self.select(raw_document.mime_type)
        parsed = parser.parse(raw_document)
        if parsed.parser_name != parser.name:
            parsed.parser_name = parser.name
        if parsed.parser_version != parser.version:
            parsed.parser_version = parser.version
        return parsed

    def identity(self, mime_type: str) -> tuple[str, int]:
        parser = self.select(mime_type)
        return parser.name, parser.version


_REGISTRY: ParserRegistry | None = None


def get_parser_registry() -> ParserRegistry:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = ParserRegistry()
    return _REGISTRY
