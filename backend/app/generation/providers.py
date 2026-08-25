"""LLM provider abstraction and deterministic extractive provider."""

from __future__ import annotations

import re
from typing import Protocol

import httpx

from app.core.config import Settings, get_settings
from app.generation.models import EvidenceStatus, GroundedAnswer
from app.retrieval.bm25 import tokenize
from app.retrieval.models import RetrievalHit

SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")
INSUFFICIENT_MESSAGE = "I could not find enough information in the connected sources."


class LLMProvider(Protocol):
    name: str

    def answer(self, *, question: str, context: list[RetrievalHit]) -> GroundedAnswer:
        """Generate a grounded answer from selected context."""


class ExtractiveLLMProvider:
    name = "extractive"

    def answer(self, *, question: str, context: list[RetrievalHit]) -> GroundedAnswer:
        if not context:
            return GroundedAnswer(
                answer=INSUFFICIENT_MESSAGE,
                evidence_status=EvidenceStatus.INSUFFICIENT,
            )
        question_terms = set(tokenize(question))
        sentences: list[str] = []
        used: list[RetrievalHit] = []
        for hit in context:
            sentence = best_sentence(hit.text, question_terms)
            if sentence:
                sentences.append(f"{sentence} [{len(used) + 1}]")
                used.append(hit)
            if len(sentences) >= 3:
                break
        if not sentences:
            return GroundedAnswer(
                answer=INSUFFICIENT_MESSAGE,
                evidence_status=EvidenceStatus.INSUFFICIENT,
            )
        return GroundedAnswer(
            answer=" ".join(sentences),
            evidence_status=EvidenceStatus.GROUNDED,
            context=used,
        )


def best_sentence(text: str, question_terms: set[str]) -> str:
    candidates = [part.strip() for part in SENTENCE_RE.split(text.strip()) if part.strip()]
    if not candidates:
        return text.strip()
    if not question_terms:
        return candidates[0]
    ranked = sorted(
        candidates,
        key=lambda item: len(question_terms.intersection(tokenize(item))),
        reverse=True,
    )
    return ranked[0]


class OpenAIChatLLMProvider:
    name = "openai"

    def __init__(self, settings: Settings | None = None) -> None:
        cfg = settings or get_settings()
        if not cfg.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required when LLM_PROVIDER=openai")
        self.settings = cfg

    def answer(self, *, question: str, context: list[RetrievalHit]) -> GroundedAnswer:
        if not context:
            return GroundedAnswer(
                answer=INSUFFICIENT_MESSAGE,
                evidence_status=EvidenceStatus.INSUFFICIENT,
            )
        response = httpx.post(
            f"{self.settings.openai_base_url.rstrip('/')}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.settings.openai_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.settings.llm_model,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are a grounded RAG assistant. Answer only from the "
                            "provided context. Cite supporting snippets with bracketed "
                            "numbers like [1]. If the context is insufficient, say so."
                        ),
                    },
                    {
                        "role": "user",
                        "content": self._prompt(question=question, context=context),
                    },
                ],
                "temperature": 0,
                "max_tokens": self.settings.llm_max_tokens,
            },
            timeout=self.settings.openai_timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        answer = payload["choices"][0]["message"]["content"].strip()
        evidence_status = (
            EvidenceStatus.INSUFFICIENT
            if "insufficient" in answer.lower()
            else EvidenceStatus.GROUNDED
        )
        return GroundedAnswer(
            answer=answer,
            evidence_status=evidence_status,
            context=context,
        )

    def _prompt(self, *, question: str, context: list[RetrievalHit]) -> str:
        snippets = "\n\n".join(
            (
                f"[{index}] {hit.title}"
                f"{f', page {hit.page}' if hit.page else ''}"
                f"{f', section {hit.section}' if hit.section else ''}\n"
                f"{hit.text}"
            )
            for index, hit in enumerate(context, start=1)
        )
        return f"Question:\n{question}\n\nContext:\n{snippets}\n\nAnswer:"


def get_llm_provider(name: str, settings: Settings | None = None) -> LLMProvider:
    if name == "openai":
        return OpenAIChatLLMProvider(settings)
    if name == "extractive":
        return ExtractiveLLMProvider()
    raise ValueError(f"unsupported LLM provider: {name}")
