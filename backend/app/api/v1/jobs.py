"""Ingestion job inspection and retry."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.v1.deps import get_current_organization, get_ingestion_service
from app.api.v1.enqueue import enqueue_outcome
from app.ingestion.errors import NotFoundError
from app.ingestion.schemas import DocumentRead, JobRead, UploadResult
from app.ingestion.service import IngestionService
from app.models.organization import Organization

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=list[JobRead])
def list_jobs(
    org: Annotated[Organization, Depends(get_current_organization)],
    service: Annotated[IngestionService, Depends(get_ingestion_service)],
    status_filter: str | None = None,
    document_id: UUID | None = None,
) -> list[JobRead]:
    jobs = service.list_jobs(org.id, status=status_filter, document_id=document_id)
    return [JobRead.model_validate(item) for item in jobs]


@router.get("/{job_id}", response_model=JobRead)
def get_job(
    job_id: UUID,
    org: Annotated[Organization, Depends(get_current_organization)],
    service: Annotated[IngestionService, Depends(get_ingestion_service)],
) -> JobRead:
    try:
        return JobRead.model_validate(service.get_job(org.id, job_id))
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/dlq/failed", response_model=list[JobRead])
def list_dead_letter_jobs(
    org: Annotated[Organization, Depends(get_current_organization)],
    service: Annotated[IngestionService, Depends(get_ingestion_service)],
) -> list[JobRead]:
    return [JobRead.model_validate(item) for item in service.list_dead_letter_jobs(org.id)]


@router.post("/dlq/{job_id}/replay", response_model=UploadResult)
def replay_dead_letter_job(
    job_id: UUID,
    org: Annotated[Organization, Depends(get_current_organization)],
    service: Annotated[IngestionService, Depends(get_ingestion_service)],
) -> UploadResult:
    try:
        outcome = service.replay_dead_letter_job(org.id, job_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    enqueue_outcome(service.session, outcome)
    return UploadResult(
        unchanged=outcome.unchanged,
        document=DocumentRead.model_validate(outcome.document),
        job=JobRead.model_validate(outcome.job),
    )


@router.post("/{job_id}/retry", response_model=UploadResult)
def retry_job(
    job_id: UUID,
    org: Annotated[Organization, Depends(get_current_organization)],
    service: Annotated[IngestionService, Depends(get_ingestion_service)],
) -> UploadResult:
    try:
        outcome = service.retry_job(org.id, job_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    enqueue_outcome(service.session, outcome)
    return UploadResult(
        unchanged=outcome.unchanged,
        document=DocumentRead.model_validate(outcome.document),
        job=JobRead.model_validate(outcome.job),
    )
