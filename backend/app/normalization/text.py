"""Deterministic text cleaning. Never lowercases stored content."""

from __future__ import annotations

import html
import unicodedata

from app.ingestion.hashing import sha256_digest

_ZERO_WIDTH = (
    "\u200b",
    "\u200c",
    "\u200d",
    "\ufeff",
)


def normalize_text(text: str, *, preserve_newlines: bool = False) -> str:
    """NFC unicode, unescape entities, fold line endings, collapse whitespace."""
    cleaned = html.unescape(text)
    cleaned = unicodedata.normalize("NFC", cleaned)
    cleaned = cleaned.replace("\r\n", "\n").replace("\r", "\n")
    cleaned = cleaned.replace("\u00a0", " ")
    for marker in _ZERO_WIDTH:
        cleaned = cleaned.replace(marker, "")
    if preserve_newlines:
        lines = [" ".join(line.split()) for line in cleaned.split("\n")]
        while lines and not lines[0]:
            lines.pop(0)
        while lines and not lines[-1]:
            lines.pop()
        return "\n".join(lines)
    return " ".join(cleaned.split())


def normalize_code(text: str) -> str:
    cleaned = html.unescape(text)
    cleaned = unicodedata.normalize("NFC", cleaned)
    cleaned = cleaned.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in cleaned.split("\n")]
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines)


def normalized_content_hash(texts: list[str]) -> str:
    blob = "\n".join(texts).encode("utf-8")
    return sha256_digest(blob)
