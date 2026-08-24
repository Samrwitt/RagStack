"""Ingestion control plane: identity, hashing, jobs, and versioning."""

from app.ingestion.hashing import sha256_digest
from app.ingestion.identity import stable_document_id
from app.ingestion.service import IngestionService, IngestOutcome

__all__ = ["IngestOutcome", "IngestionService", "sha256_digest", "stable_document_id"]
