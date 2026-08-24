"""Cleaning, Unicode normalization, boilerplate removal, and deduplication.

Phase 4 implements exact SHA-256 duplicates and optional near-duplicate
detection (SimHash) without silently deleting related documents.
"""

from app.normalization.language import detect_language
from app.normalization.models import NormalizedDocument
from app.normalization.pipeline import normalize_blocks
from app.normalization.simhash import hamming_distance, simhash64
from app.normalization.text import normalize_text

__all__ = [
    "NormalizedDocument",
    "detect_language",
    "hamming_distance",
    "normalize_blocks",
    "normalize_text",
    "simhash64",
]
