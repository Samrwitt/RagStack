"""Parser contract. Implementations live beside this module, not behind a framework."""

from typing import Protocol

from app.parsers.models import ParsedDocument, RawDocument


class DocumentParser(Protocol):
    name: str
    version: int

    def supports(self, mime_type: str) -> bool:
        """Return True when this parser owns the MIME type."""

    def parse(self, raw_document: RawDocument) -> ParsedDocument:
        """Turn raw bytes into structured blocks."""
