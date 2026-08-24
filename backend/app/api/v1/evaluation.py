"""Evaluation endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_organization, get_sync_session
from app.evaluation.schemas import (
    EvaluationCompareRequest,
    EvaluationCompareResponse,
    EvaluationRunCreate,
    EvaluationRunRead,
)
from app.evaluation.service import EvaluationService
from app.models.organization import Organization

router = APIRouter(prefix="/evaluation", tags=["evaluation"])


@router.post("/run", response_model=EvaluationRunRead)
def run_evaluation(
    payload: EvaluationRunCreate,
    org: Annotated[Organization, Depends(get_current_organization)],
    session: Annotated[Session, Depends(get_sync_session)],
) -> EvaluationRunRead:
    run = EvaluationService(session).run(
        organization_id=org.id,
        name=payload.name,
        dataset=payload.dataset,
        config=payload.config,
    )
    return EvaluationRunRead.model_validate(run)


@router.get("/runs", response_model=list[EvaluationRunRead])
def list_evaluation_runs(
    org: Annotated[Organization, Depends(get_current_organization)],
    session: Annotated[Session, Depends(get_sync_session)],
) -> list[EvaluationRunRead]:
    runs = EvaluationService(session).list_runs(org.id)
    return [EvaluationRunRead.model_validate(item) for item in runs]


@router.get("/runs/{run_id}", response_model=EvaluationRunRead)
def get_evaluation_run(
    run_id: UUID,
    org: Annotated[Organization, Depends(get_current_organization)],
    session: Annotated[Session, Depends(get_sync_session)],
) -> EvaluationRunRead:
    run = EvaluationService(session).get_run(org.id, run_id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="evaluation run not found",
        )
    return EvaluationRunRead.model_validate(run)


@router.post("/compare", response_model=EvaluationCompareResponse)
def compare_evaluation_runs(
    payload: EvaluationCompareRequest,
    org: Annotated[Organization, Depends(get_current_organization)],
    session: Annotated[Session, Depends(get_sync_session)],
) -> EvaluationCompareResponse:
    rows = EvaluationService(session).compare(org.id, payload.run_ids)
    return EvaluationCompareResponse(rows=rows)
