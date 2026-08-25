"""Embedding and vector indexing endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.v1.deps import (
    AuthenticatedPrincipal,
    get_ingestion_service,
    get_sync_session,
    require_permission,
)
from app.auth.rbac import Permission
from app.embeddings.schemas import EmbeddingTaskRead, StaleEmbeddingRead
from app.embeddings.service import EmbeddingService
from app.ingestion.errors import NotFoundError
from app.ingestion.service import IngestionService

router = APIRouter(prefix="/embeddings", tags=["embeddings"])


@router.get("/stale", response_model=StaleEmbeddingRead)
def list_stale_embeddings(
    principal: Annotated[AuthenticatedPrincipal, Depends(require_permission(Permission.ADMIN))],
    session: Annotated[Session, Depends(get_sync_session)],
) -> StaleEmbeddingRead:
    service = EmbeddingService(session)
    document_ids = service.stale_document_ids(principal.organization.id)
    return StaleEmbeddingRead(document_ids=document_ids, count=len(document_ids))


@router.post("/documents/{document_id}", response_model=EmbeddingTaskRead)
def enqueue_document_embedding(
    document_id: UUID,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_permission(Permission.WRITE))],
    ingestion: Annotated[IngestionService, Depends(get_ingestion_service)],
) -> EmbeddingTaskRead:
    try:
        ingestion.get_document(principal.organization.id, document_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    from app.workers.embedding import embed_document

    result = embed_document.delay(str(document_id))
    return EmbeddingTaskRead(
        document_id=document_id,
        celery_task_id=result.id,
        action="embed",
    )


@router.delete("/documents/{document_id}/vectors", response_model=EmbeddingTaskRead)
def enqueue_document_vector_delete(
    document_id: UUID,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_permission(Permission.ADMIN))],
    ingestion: Annotated[IngestionService, Depends(get_ingestion_service)],
) -> EmbeddingTaskRead:
    try:
        ingestion.get_document(principal.organization.id, document_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    from app.workers.embedding import delete_document_vectors

    result = delete_document_vectors.delay(str(document_id))
    return EmbeddingTaskRead(
        document_id=document_id,
        celery_task_id=result.id,
        action="delete_vectors",
    )
