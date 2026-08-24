"""Content hashing for idempotent ingestion.

Phase 2 hashes original bytes. Phase 4 will add a separate hash of
normalized text; both remain stored so replay stays deterministic.
"""

import hashlib


def sha256_digest(data: bytes) -> str:
    """Return the lowercase hex SHA-256 digest of raw bytes."""
    return hashlib.sha256(data).hexdigest()
