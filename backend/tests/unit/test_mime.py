import pytest

from app.core.config import Settings
from app.ingestion.mime import UnsupportedUpload, resolve_mime, validate_upload


def test_resolve_mime_from_extension() -> None:
    assert resolve_mime("handbook.md", "application/octet-stream") == "text/markdown"


def test_validate_rejects_empty() -> None:
    with pytest.raises(UnsupportedUpload):
        validate_upload(filename="a.txt", declared_mime="text/plain", size_bytes=0)


def test_validate_rejects_unknown_type() -> None:
    settings = Settings(allowed_upload_mime_types="text/plain")
    with pytest.raises(UnsupportedUpload):
        validate_upload(
            filename="photo.png",
            declared_mime="image/png",
            size_bytes=12,
            settings=settings,
        )


def test_validate_accepts_markdown() -> None:
    mime = validate_upload(filename="runbook.md", declared_mime=None, size_bytes=20)
    assert mime == "text/markdown"
