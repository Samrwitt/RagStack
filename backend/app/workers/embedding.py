"""Celery task for embedding and indexing document chunks."""

from typing import Any
from uuid import UUID

from app.core.db import get_sync_session_factory
from app.core.logging import get_logger
from app.embeddings.service import EmbeddingService
from app.ingestion.errors import NotFoundError
from app.workers.celery_app import celery_app

logger = get_logger(__name__)


@celery_app.task(name="app.workers.embedding.embed_document", bind=True, max_retries=3)
def embed_document(self: Any, document_id: str) -> dict[str, str | int]:
    factory = get_sync_session_factory()
    with factory() as session:
        service = EmbeddingService(session)
        try:
            outcome = service.embed_current_document(UUID(document_id))
            session.commit()
        except NotFoundError:
            session.commit()
            logger.exception("embedding.document_not_found", document_id=document_id)
            raise
        except Exception as exc:
            session.commit()
            logger.exception("embedding.document_failed", document_id=document_id)
            raise self.retry(exc=exc, countdown=min(2**self.request.retries, 30)) from exc

    return {
        "document_id": str(outcome.document_id),
        "version_id": str(outcome.version_id),
        "chunk_count": outcome.chunk_count,
        "collection": outcome.collection_name,
        "provider": outcome.provider,
        "model": outcome.model,
        "dimensions": outcome.dimensions,
    }
