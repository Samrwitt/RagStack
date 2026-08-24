"""Stable document identity.

The same upstream item must resolve to the same document ID across
discoveries so ingestion is an upsert, not a duplicate insert.
"""

from uuid import UUID, uuid5

# Namespace UUID for CorpusForge document IDs (RFC 4122 UUID5).
DOCUMENT_NAMESPACE = UUID("6ba7b814-9dad-41d1-80b4-00c04fd430c8")


def stable_document_id(
    organization_id: UUID,
    source: str,
    source_connection_id: UUID,
    source_id: str,
) -> UUID:
    """Derive a deterministic UUID from tenant + source coordinates."""
    material = "|".join(
        (
            str(organization_id),
            source.strip().lower(),
            str(source_connection_id),
            source_id.strip(),
        )
    )
    return uuid5(DOCUMENT_NAMESPACE, material)


def normalize_source_id(source_id: str) -> str:
    """Collapse path-like upload names into a stable upstream identifier."""
    cleaned = source_id.strip().replace("\\", "/")
    while "//" in cleaned:
        cleaned = cleaned.replace("//", "/")
    return cleaned.lstrip("/")
