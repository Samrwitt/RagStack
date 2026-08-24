"""Pydantic schemas for evaluation APIs."""

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class EvalRecord(BaseModel):
    question: str = Field(min_length=1)
    expected_answer: str = ""
    relevant_document_ids: list[UUID] = Field(default_factory=list)


class EvaluationConfig(BaseModel):
    mode: Literal["dense", "sparse", "hybrid"] = "hybrid"
    top_k: int = Field(default=10, ge=1, le=50)
    candidate_k: int = Field(default=50, ge=1, le=200)
    rerank: bool = True
    generate: bool = True


class EvaluationRunCreate(BaseModel):
    name: str = Field(default="ad hoc", min_length=1, max_length=255)
    dataset: list[EvalRecord] = Field(min_length=1)
    config: EvaluationConfig = Field(default_factory=EvaluationConfig)


class EvaluationRunRead(BaseModel):
    id: UUID
    name: str
    status: str
    config: dict[str, Any]
    metrics: dict[str, float]
    results: list[dict[str, Any]]

    model_config = {"from_attributes": True}


class EvaluationCompareRequest(BaseModel):
    run_ids: list[UUID] = Field(min_length=1)


class EvaluationCompareResponse(BaseModel):
    rows: list[dict[str, Any]]
