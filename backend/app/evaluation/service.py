"""Evaluation run orchestration."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.evaluation.metrics import (
    citation_completeness,
    citation_correctness,
    groundedness,
    mean,
    mrr,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
)
from app.evaluation.schemas import EvalRecord, EvaluationConfig
from app.generation.models import ChatMessage
from app.generation.service import GenerationService
from app.models.evaluation import EvaluationRun
from app.retrieval.models import ACLContext, RetrievalFilters, RetrievalMode, RetrievalRequest
from app.retrieval.service import RetrievalService


class EvaluationService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def run(
        self,
        *,
        organization_id: UUID,
        name: str,
        dataset: list[EvalRecord],
        config: EvaluationConfig,
        acl: ACLContext | None = None,
    ) -> EvaluationRun:
        retrieval = RetrievalService(self.session)
        generation = GenerationService(self.session)
        rows: list[dict] = []
        aggregate: dict[str, list[float]] = {
            "recall_at_k": [],
            "precision_at_k": [],
            "mrr": [],
            "ndcg_at_k": [],
            "groundedness": [],
            "citation_correctness": [],
            "citation_completeness": [],
        }
        for record in dataset:
            filters = RetrievalFilters(organization_id=organization_id)
            request = RetrievalRequest(
                query=record.question,
                filters=filters,
                mode=RetrievalMode(config.mode),
                top_k=config.top_k,
                candidate_k=config.candidate_k,
                acl=acl or ACLContext(),
                rerank=config.rerank,
            )
            hits, context = retrieval.search_with_context(request)
            retrieved_doc_ids = [str(hit.document_id) for hit in hits]
            relevant = {str(item) for item in record.relevant_document_ids}
            row = {
                "question": record.question,
                "expected_answer": record.expected_answer,
                "retrieved_document_ids": retrieved_doc_ids,
                "relevant_document_ids": sorted(relevant),
                "recall_at_k": recall_at_k(retrieved_doc_ids, relevant, config.top_k),
                "precision_at_k": precision_at_k(retrieved_doc_ids, relevant, config.top_k),
                "mrr": mrr(retrieved_doc_ids, relevant),
                "ndcg_at_k": ndcg_at_k(retrieved_doc_ids, relevant, config.top_k),
            }
            if config.generate:
                answer = generation.answer(
                    question=record.question,
                    history=[ChatMessage(role="user", content=record.question)],
                    filters=filters,
                    mode=RetrievalMode(config.mode),
                    top_k=config.top_k,
                    candidate_k=config.candidate_k,
                    rerank=config.rerank,
                    acl=acl,
                )
                cited = [str(item.document_id) for item in answer.citations]
                row.update(
                    {
                        "answer": answer.answer,
                        "evidence_status": answer.evidence_status.value,
                        "groundedness": groundedness(
                            answer.answer,
                            [item.hit.text for item in context],
                        ),
                        "citation_correctness": citation_correctness(cited, relevant),
                        "citation_completeness": citation_completeness(cited, relevant),
                    }
                )
            rows.append(row)
            for key, values in aggregate.items():
                if key in row:
                    values.append(float(row[key]))
        metrics = {key: mean(values) for key, values in aggregate.items()}
        run = EvaluationRun(
            organization_id=organization_id,
            name=name,
            status="SUCCEEDED",
            config=config.model_dump(),
            dataset=[item.model_dump(mode="json") for item in dataset],
            results=rows,
            metrics=metrics,
        )
        self.session.add(run)
        self.session.flush()
        return run

    def list_runs(self, organization_id: UUID) -> list[EvaluationRun]:
        return list(
            self.session.scalars(
                select(EvaluationRun)
                .where(EvaluationRun.organization_id == organization_id)
                .order_by(EvaluationRun.created_at.desc())
            ).all()
        )

    def get_run(self, organization_id: UUID, run_id: UUID) -> EvaluationRun | None:
        run = self.session.get(EvaluationRun, run_id)
        if run is None or run.organization_id != organization_id:
            return None
        return run

    def compare(self, organization_id: UUID, run_ids: list[UUID]) -> list[dict]:
        rows: list[dict] = []
        for run_id in run_ids:
            run = self.get_run(organization_id, run_id)
            if run is None:
                continue
            rows.append({"id": str(run.id), "name": run.name, **run.metrics})
        return rows
