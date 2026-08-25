"""Ingestion job inspection and retry."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.v1.deps import AuthenticatedPrincipal, get_ingestion_service, require_permission
from app.api.v1.enqueue import enqueue_outcome
from app.auth.rbac import Permission
from app.ingestion.errors import NotFoundError
from app.ingestion.schemas import DocumentRead, JobRead, UploadResult
from app.ingestion.service import IngestionService

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=list[JobRead])
def list_jobs(
    principal: Annotated[AuthenticatedPrincipal, Depends(require_permission(Permission.READ))],
    service: Annotated[IngestionService, Depends(get_ingestion_service)],
    status_filter: str | None = None,
    document_id: UUID | None = None,
) -> list[JobRead]:
    jobs = service.list_jobs(
        principal.organization.id,
        status=status_filter,
        document_id=document_id,
    )
    return [JobRead.model_validate(item) for item in jobs]


@router.get("/dlq/failed", response_model=list[JobRead])
def list_dead_letter_jobs(
    principal: Annotated[AuthenticatedPrincipal, Depends(require_permission(Permission.READ))],
    service: Annotated[IngestionService, Depends(get_ingestion_service)],
) -> list[JobRead]:
    return [
        JobRead.model_validate(item)
        for item in service.list_dead_letter_jobs(principal.organization.id)
    ]


@router.post("/dlq/{job_id}/replay", response_model=UploadResult)
def replay_dead_letter_job(
    job_id: UUID,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_permission(Permission.WRITE))],
    service: Annotated[IngestionService, Depends(get_ingestion_service)],
) -> UploadResult:
    try:
        outcome = service.replay_dead_letter_job(principal.organization.id, job_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    enqueue_outcome(service.session, outcome)
    return UploadResult(
        unchanged=outcome.unchanged,
        document=DocumentRead.model_validate(outcome.document),
        job=JobRead.model_validate(outcome.job),
    )


@router.get("/{job_id}", response_model=JobRead)
def get_job(
    job_id: UUID,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_permission(Permission.READ))],
    service: Annotated[IngestionService, Depends(get_ingestion_service)],
) -> JobRead:
    try:
        return JobRead.model_validate(service.get_job(principal.organization.id, job_id))
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/{job_id}/retry", response_model=UploadResult)
def retry_job(
    job_id: UUID,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_permission(Permission.WRITE))],
    service: Annotated[IngestionService, Depends(get_ingestion_service)],
) -> UploadResult:
    try:
        outcome = service.retry_job(principal.organization.id, job_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    enqueue_outcome(service.session, outcome)
    return UploadResult(
        unchanged=outcome.unchanged,
        document=DocumentRead.model_validate(outcome.document),
        job=JobRead.model_validate(outcome.job),
    )
