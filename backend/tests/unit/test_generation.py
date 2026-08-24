from uuid import uuid4

from app.generation.citations import resolve_citations
from app.generation.models import ChatMessage, EvidenceStatus
from app.generation.providers import INSUFFICIENT_MESSAGE, ExtractiveLLMProvider
from app.generation.service import conversation_retrieval_query
from app.retrieval.models import RetrievalHit


def _hit(text: str) -> RetrievalHit:
    return RetrievalHit(
        chunk_id=uuid4(),
        document_id=uuid4(),
        version_id=uuid4(),
        score=0.9,
        rank=1,
        text=text,
        title="Handbook",
        source_type="file_upload",
        source_url="https://example.test/handbook",
        page=3,
        section="Leave",
        metadata={},
        scores={"reranker": 0.9},
    )


def test_extractive_provider_returns_insufficient_evidence_without_context() -> None:
    answer = ExtractiveLLMProvider().answer(question="How many leave days?", context=[])

    assert answer.evidence_status == EvidenceStatus.INSUFFICIENT
    assert answer.answer == INSUFFICIENT_MESSAGE


def test_extractive_provider_answers_with_inline_citation_markers() -> None:
    hit = _hit("Employees receive 22 annual leave days. Expenses are separate.")

    answer = ExtractiveLLMProvider().answer(
        question="How many annual leave days?",
        context=[hit],
    )

    assert answer.evidence_status == EvidenceStatus.GROUNDED
    assert answer.answer == "Employees receive 22 annual leave days. [1]"
    assert answer.context == [hit]


def test_resolve_citations_deduplicates_hits() -> None:
    hit = _hit("Employees receive 22 annual leave days.")

    citations = resolve_citations([hit, hit])

    assert len(citations) == 1
    assert citations[0].title == "Handbook"
    assert citations[0].page == 3


def test_conversation_retrieval_query_uses_recent_history() -> None:
    query = conversation_retrieval_query(
        "What changed?",
        [
            ChatMessage(role="user", content="Tell me about leave."),
            ChatMessage(role="assistant", content="The handbook has a leave section."),
        ],
    )

    assert query == "Tell me about leave. The handbook has a leave section. What changed?"
