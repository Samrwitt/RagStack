"""Parse failures. Permanent errors must not be retried by Celery."""

from app.ingestion.errors import IngestionError


class ParseError(IngestionError):
    """Base class for parser failures."""


class PermanentParseError(ParseError):
    """Corrupt file, unsupported MIME, or unrecoverable extract failure."""


class UnsupportedMimeError(PermanentParseError):
    def __init__(self, mime_type: str) -> None:
        self.mime_type = mime_type
        super().__init__(f"no parser registered for MIME type {mime_type!r}")
