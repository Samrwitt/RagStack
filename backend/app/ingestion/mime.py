"""Upload validation: extension, declared MIME, and size."""

from pathlib import Path

from app.core.config import Settings, get_settings

EXTENSION_MIME: dict[str, str] = {
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".markdown": "text/markdown",
    ".html": "text/html",
    ".htm": "text/html",
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}

MIME_ALIASES: dict[str, str] = {
    "text/x-markdown": "text/markdown",
    "application/x-pdf": "application/pdf",
    "application/octet-stream": "application/octet-stream",
}


class UnsupportedUpload(ValueError):
    """Permanent rejection — do not retry."""


def canonicalize_mime(mime_type: str | None) -> str | None:
    if not mime_type:
        return None
    cleaned = mime_type.split(";")[0].strip().lower()
    return MIME_ALIASES.get(cleaned, cleaned)


def mime_from_filename(filename: str) -> str | None:
    suffix = Path(filename).suffix.lower()
    return EXTENSION_MIME.get(suffix)


def resolve_mime(filename: str, declared: str | None) -> str:
    from_name = mime_from_filename(filename)
    from_declared = canonicalize_mime(declared)
    if from_declared and from_declared != "application/octet-stream":
        if from_name and from_declared != from_name:
            # Trust the extension for known document types; declared type can lie.
            return from_name
        return from_declared
    if from_name:
        return from_name
    raise UnsupportedUpload(f"cannot determine MIME type for {filename!r}")


def allowed_mime_types(settings: Settings | None = None) -> set[str]:
    cfg = settings or get_settings()
    return {
        part.strip().lower() for part in cfg.allowed_upload_mime_types.split(",") if part.strip()
    }


def validate_upload(
    *,
    filename: str,
    declared_mime: str | None,
    size_bytes: int,
    settings: Settings | None = None,
) -> str:
    cfg = settings or get_settings()
    if size_bytes <= 0:
        raise UnsupportedUpload("empty uploads are not allowed")
    if size_bytes > cfg.max_upload_size_bytes:
        raise UnsupportedUpload(f"file exceeds maximum size of {cfg.max_upload_size_bytes} bytes")
    mime = resolve_mime(filename, declared_mime)
    allowed = allowed_mime_types(cfg)
    if mime not in allowed:
        raise UnsupportedUpload(f"MIME type {mime!r} is not allowed")
    return mime
