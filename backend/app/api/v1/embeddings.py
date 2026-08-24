"""Embedding and vector indexing endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_organization, get_ingestion_service, get_sync_session
from app.embeddings.schemas import EmbeddingTaskRead, StaleEmbeddingRead
from app.embeddings.service import EmbeddingService
from app.ingestion.errors import NotFoundError
from app.ingestion.service import IngestionService
from app.models.organization import Organization
from app.workers.embedding import delete_document_vectors, embed_document

router = APIRouter(prefix="/embeddings", tags=["embeddings"])


@router.get("/stale", response_model=StaleEmbeddingRead)
def list_stale_embeddings(
    org: Annotated[Organization, Depends(get_current_organization)],
    session: Annotated[Session, Depends(get_sync_session)],
) -> StaleEmbeddingRead:
    service = EmbeddingService(session)
    document_ids = service.stale_document_ids(org.id)
    return StaleEmbeddingRead(document_ids=document_ids, count=len(document_ids))


@router.post("/documents/{document_id}", response_model=EmbeddingTaskRead)
def enqueue_document_embedding(
    document_id: UUID,
    org: Annotated[Organization, Depends(get_current_organization)],
    ingestion: Annotated[IngestionService, Depends(get_ingestion_service)],
) -> EmbeddingTaskRead:
    try:
        ingestion.get_document(org.id, document_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    result = embed_document.delay(str(document_id))
    return EmbeddingTaskRead(
        document_id=document_id,
        celery_task_id=result.id,
        action="embed",
    )


@router.delete("/documents/{document_id}/vectors", response_model=EmbeddingTaskRead)
def enqueue_document_vector_delete(
    document_id: UUID,
    org: Annotated[Organization, Depends(get_current_organization)],
    ingestion: Annotated[IngestionService, Depends(get_ingestion_service)],
) -> EmbeddingTaskRead:
    try:
        ingestion.get_document(org.id, document_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    result = delete_document_vectors.delay(str(document_id))
    return EmbeddingTaskRead(
        document_id=document_id,
        celery_task_id=result.id,
        action="delete_vectors",
    )
