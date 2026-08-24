"""Ingestion control plane: identity, hashing, jobs, and versioning."""

from app.ingestion.hashing import sha256_digest
from app.ingestion.identity import stable_document_id

__all__ = ["IngestOutcome", "IngestionService", "sha256_digest", "stable_document_id"]


def __getattr__(name: str):
    if name in {"IngestionService", "IngestOutcome"}:
        from app.ingestion.service import IngestOutcome, IngestionService

        return IngestionService if name == "IngestionService" else IngestOutcome
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
