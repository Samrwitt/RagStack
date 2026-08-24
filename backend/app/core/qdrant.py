"""Qdrant client for later dense/sparse indexing.

Collections are not created here. Phase 6 owns vector schema, named vectors,
and embedding-model compatibility. Phase 1 only verifies connectivity.
"""

from qdrant_client import QdrantClient

from app.core.config import Settings, get_settings

_client: QdrantClient | None = None


def get_qdrant_client(settings: Settings | None = None) -> QdrantClient:
    global _client
    if _client is None:
        cfg = settings or get_settings()
        _client = QdrantClient(url=cfg.qdrant_url, api_key=cfg.qdrant_api_key_or_none)
    return _client


def ping_qdrant(settings: Settings | None = None) -> int:
    """Return the number of collections as a cheap connectivity probe."""
    client = get_qdrant_client(settings)
    collections = client.get_collections()
    return len(collections.collections)


def close_qdrant() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None
