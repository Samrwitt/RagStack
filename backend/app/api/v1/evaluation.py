"""Evaluation endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.v1.deps import AuthenticatedPrincipal, get_sync_session, require_permission
from app.auth.rbac import Permission
from app.evaluation.schemas import (
    EvaluationCompareRequest,
    EvaluationCompareResponse,
    EvaluationRunCreate,
    EvaluationRunRead,
)
from app.evaluation.service import EvaluationService

router = APIRouter(prefix="/evaluation", tags=["evaluation"])


@router.post("/run", response_model=EvaluationRunRead)
def run_evaluation(
    payload: EvaluationRunCreate,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_permission(Permission.ADMIN))],
    session: Annotated[Session, Depends(get_sync_session)],
) -> EvaluationRunRead:
    run = EvaluationService(session).run(
        organization_id=principal.organization.id,
        name=payload.name,
        dataset=payload.dataset,
        config=payload.config,
        acl=principal.acl,
    )
    return EvaluationRunRead.model_validate(run)


@router.post("/experiment", response_model=list[EvaluationRunRead])
def run_experiment(
    payload: EvaluationRunCreate,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_permission(Permission.ADMIN))],
    session: Annotated[Session, Depends(get_sync_session)],
) -> list[EvaluationRunRead]:
    runs = EvaluationService(session).run_experiment(
        organization_id=principal.organization.id,
        name=payload.name,
        dataset=payload.dataset,
        acl=principal.acl,
    )
    return [EvaluationRunRead.model_validate(item) for item in runs]


@router.get("/runs", response_model=list[EvaluationRunRead])
def list_evaluation_runs(
    principal: Annotated[AuthenticatedPrincipal, Depends(require_permission(Permission.READ))],
    session: Annotated[Session, Depends(get_sync_session)],
) -> list[EvaluationRunRead]:
    runs = EvaluationService(session).list_runs(principal.organization.id)
    return [EvaluationRunRead.model_validate(item) for item in runs]


@router.get("/runs/{run_id}", response_model=EvaluationRunRead)
def get_evaluation_run(
    run_id: UUID,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_permission(Permission.READ))],
    session: Annotated[Session, Depends(get_sync_session)],
) -> EvaluationRunRead:
    run = EvaluationService(session).get_run(principal.organization.id, run_id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="evaluation run not found",
        )
    return EvaluationRunRead.model_validate(run)


@router.post("/compare", response_model=EvaluationCompareResponse)
def compare_evaluation_runs(
    payload: EvaluationCompareRequest,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_permission(Permission.READ))],
    session: Annotated[Session, Depends(get_sync_session)],
) -> EvaluationCompareResponse:
    rows = EvaluationService(session).compare(principal.organization.id, payload.run_ids)
    return EvaluationCompareResponse(rows=rows)
