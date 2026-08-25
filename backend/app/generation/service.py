"""Conversation-aware retrieval plus grounded generation."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.generation.citations import resolve_citations
from app.generation.models import ChatMessage, EvidenceStatus, GroundedAnswer
from app.generation.providers import LLMProvider, get_llm_provider
from app.retrieval.models import RetrievalFilters, RetrievalMode, RetrievalRequest
from app.retrieval.service import RetrievalService


class GenerationService:
    def __init__(
        self,
        session: Session,
        *,
        provider: LLMProvider | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.session = session
        self.settings = settings or get_settings()
        self.provider = provider or get_llm_provider(self.settings.llm_provider, self.settings)
        self.retrieval = RetrievalService(session, settings=self.settings)

    def answer(
        self,
        *,
        question: str,
        history: list[ChatMessage],
        filters: RetrievalFilters,
        mode: RetrievalMode = RetrievalMode.HYBRID,
        top_k: int = 8,
        candidate_k: int | None = None,
        rerank: bool = True,
    ) -> GroundedAnswer:
        retrieval_query = conversation_retrieval_query(question, history)
        request = RetrievalRequest(
            query=retrieval_query,
            filters=filters,
            mode=mode,
            top_k=top_k,
            candidate_k=candidate_k or self.settings.reranker_candidate_k,
            rerank=rerank,
            context_token_budget=self.settings.context_token_budget,
        )
        hits, selected = self.retrieval.search_with_context(request)
        context = [item.hit for item in selected]
        best_score = max((hit.score for hit in hits), default=0.0)
        if not context or best_score < self.settings.min_grounding_score:
            return GroundedAnswer(
                answer=self.provider.answer(question=question, context=[]).answer,
                evidence_status=EvidenceStatus.INSUFFICIENT,
                retrieval_query=retrieval_query,
            )
        answer = self.provider.answer(question=question, context=context)
        answer_context = answer.context or context
        citations = resolve_citations(answer_context)
        return GroundedAnswer(
            answer=answer.answer,
            evidence_status=answer.evidence_status,
            citations=citations,
            context=answer_context,
            retrieval_query=retrieval_query,
        )


def conversation_retrieval_query(question: str, history: list[ChatMessage]) -> str:
    useful_history = [
        item.content.strip()
        for item in history[-4:]
        if item.role in {"user", "assistant"} and item.content.strip()
    ]
    if not useful_history:
        return question
    return " ".join([*useful_history, question])
