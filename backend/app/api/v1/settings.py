"""Settings API endpoints."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.v1.deps import AuthenticatedPrincipal, require_permission
from app.auth.rbac import Permission
from app.core.config import get_settings

router = APIRouter(prefix="/settings", tags=["settings"])


class SettingsRead(BaseModel):
    reranker_enabled: bool
    reranker_provider: str
    llm_provider: str
    reranker_candidate_k: int
    context_token_budget: int
    min_grounding_score: float


class SettingsUpdate(BaseModel):
    reranker_enabled: bool | None = None
    reranker_candidate_k: int | None = Field(default=None, ge=1, le=200)
    context_token_budget: int | None = Field(default=None, ge=1, le=32000)
    min_grounding_score: float | None = Field(default=None, ge=0.0, le=1.0)


@router.get("", response_model=SettingsRead)
def get_runtime_settings(
    principal: Annotated[AuthenticatedPrincipal, Depends(require_permission(Permission.READ))],
) -> SettingsRead:
    settings = get_settings()
    return SettingsRead(
        reranker_enabled=settings.reranker_enabled,
        reranker_provider=settings.reranker_provider,
        llm_provider=settings.llm_provider,
        reranker_candidate_k=settings.reranker_candidate_k,
        context_token_budget=settings.context_token_budget,
        min_grounding_score=settings.min_grounding_score,
    )


@router.post("", response_model=SettingsRead)
def update_runtime_settings(
    payload: SettingsUpdate,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_permission(Permission.ADMIN))],
) -> SettingsRead:
    settings = get_settings()
    if payload.reranker_enabled is not None:
        settings.reranker_enabled = payload.reranker_enabled
    if payload.reranker_candidate_k is not None:
        settings.reranker_candidate_k = payload.reranker_candidate_k
    if payload.context_token_budget is not None:
        settings.context_token_budget = payload.context_token_budget
    if payload.min_grounding_score is not None:
        settings.min_grounding_score = payload.min_grounding_score

    return SettingsRead(
        reranker_enabled=settings.reranker_enabled,
        reranker_provider=settings.reranker_provider,
        llm_provider=settings.llm_provider,
        reranker_candidate_k=settings.reranker_candidate_k,
        context_token_budget=settings.context_token_budget,
        min_grounding_score=settings.min_grounding_score,
    )
