"""Source connection endpoints."""

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.v1.deps import get_current_organization, get_ingestion_service
from app.core.bootstrap import DEV_WORKSPACE_ID
from app.ingestion.errors import IngestionError, NotFoundError
from app.ingestion.schemas import SourceCreate, SourceRead
from app.ingestion.service import IngestionService
from app.models.enums import SourceStatus
from app.models.organization import Organization

router = APIRouter(prefix="/sources", tags=["sources"])


@router.get("", response_model=list[SourceRead])
def list_sources(
    org: Annotated[Organization, Depends(get_current_organization)],
    service: Annotated[IngestionService, Depends(get_ingestion_service)],
) -> list[SourceRead]:
    return [SourceRead.model_validate(item) for item in service.list_sources(org.id)]


@router.post("", response_model=SourceRead, status_code=status.HTTP_201_CREATED)
def create_source(
    payload: SourceCreate,
    org: Annotated[Organization, Depends(get_current_organization)],
    service: Annotated[IngestionService, Depends(get_ingestion_service)],
) -> SourceRead:
    workspace_id = payload.workspace_id or DEV_WORKSPACE_ID
    try:
        source = service.create_source(
            organization_id=org.id,
            workspace_id=workspace_id,
            name=payload.name,
            source_type=payload.source_type,
            config=payload.config,
        )
    except IngestionError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return SourceRead.model_validate(source)


@router.get("/{source_id}", response_model=SourceRead)
def get_source(
    source_id: UUID,
    org: Annotated[Organization, Depends(get_current_organization)],
    service: Annotated[IngestionService, Depends(get_ingestion_service)],
) -> SourceRead:
    try:
        return SourceRead.model_validate(service.get_source(org.id, source_id))
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/{source_id}/sync", response_model=SourceRead)
def sync_source(
    source_id: UUID,
    org: Annotated[Organization, Depends(get_current_organization)],
    service: Annotated[IngestionService, Depends(get_ingestion_service)],
) -> SourceRead:
    """File-upload sources have nothing to crawl; this records a sync heartbeat."""
    try:
        source = service.get_source(org.id, source_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    source.last_sync_at = datetime.now(UTC)
    return SourceRead.model_validate(source)


@router.post("/{source_id}/pause", response_model=SourceRead)
def pause_source(
    source_id: UUID,
    org: Annotated[Organization, Depends(get_current_organization)],
    service: Annotated[IngestionService, Depends(get_ingestion_service)],
) -> SourceRead:
    try:
        source = service.set_source_status(org.id, source_id, SourceStatus.PAUSED)
        return SourceRead.model_validate(source)
    except IngestionError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/{source_id}/resume", response_model=SourceRead)
def resume_source(
    source_id: UUID,
    org: Annotated[Organization, Depends(get_current_organization)],
    service: Annotated[IngestionService, Depends(get_ingestion_service)],
) -> SourceRead:
    try:
        return SourceRead.model_validate(
            service.set_source_status(org.id, source_id, SourceStatus.CONNECTED)
        )
    except IngestionError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_source(
    source_id: UUID,
    org: Annotated[Organization, Depends(get_current_organization)],
    service: Annotated[IngestionService, Depends(get_ingestion_service)],
) -> None:
    try:
        service.delete_source(org.id, source_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
