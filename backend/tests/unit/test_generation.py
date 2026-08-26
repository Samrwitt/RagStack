from uuid import uuid4

import httpx
import pytest

from app.core.config import Settings
from app.generation.citations import resolve_citations
from app.generation.models import ChatMessage, EvidenceStatus
from app.generation.providers import (
    INSUFFICIENT_MESSAGE,
    ExtractiveLLMProvider,
    GeminiLLMProvider,
    OpenAIChatLLMProvider,
    get_llm_provider,
)
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


def test_openai_chat_provider_sends_grounded_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = {}

    def fake_post(url, *, headers, json, timeout):  # noqa: ANN001
        captured.update(url=url, headers=headers, json=json, timeout=timeout)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "Employees receive 22 days. [1]"}}]},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    hit = _hit("Employees receive 22 annual leave days.")
    provider = OpenAIChatLLMProvider(Settings(openai_api_key="key", llm_provider="openai"))

    answer = provider.answer(question="How many leave days?", context=[hit])

    assert captured["url"] == "https://api.openai.com/v1/chat/completions"
    assert captured["json"]["messages"][1]["content"].count("[1]") >= 1
    assert answer.evidence_status == EvidenceStatus.GROUNDED
    assert answer.answer == "Employees receive 22 days. [1]"


def test_gemini_provider_sends_grounded_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = {}

    def fake_post(url, *, params, headers, json, timeout):  # noqa: ANN001
        captured.update(url=url, params=params, headers=headers, json=json, timeout=timeout)
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "parts": [{"text": "Employees receive 22 days of leave per year. [1]"}]
                        }
                    }
                ]
            },
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    hit = _hit("Employees receive 22 annual leave days.")
    provider = GeminiLLMProvider(Settings(gemini_api_key="gemini_secret", llm_provider="gemini"))

    answer = provider.answer(question="How many leave days?", context=[hit])

    assert "gemini-" in captured["url"]
    assert captured["params"]["key"] == "gemini_secret"
    assert answer.evidence_status == EvidenceStatus.GROUNDED
    assert answer.answer == "Employees receive 22 days of leave per year. [1]"


def test_get_llm_provider_resolves_gemini() -> None:
    provider = get_llm_provider("gemini", Settings(gemini_api_key="key", llm_provider="gemini"))
    assert provider.name == "gemini"


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

