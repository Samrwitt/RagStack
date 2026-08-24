"""Content hashing for idempotent ingestion.

Raw-byte SHA-256 skips unchanged files. Normalized-text SHA-256 records
cross-document exact duplicates without deleting either copy.
"""

import hashlib


def sha256_digest(data: bytes) -> str:
    """Return the lowercase hex SHA-256 digest of raw bytes."""
    return hashlib.sha256(data).hexdigest()
