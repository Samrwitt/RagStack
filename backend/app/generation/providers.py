"""LLM provider abstraction and deterministic extractive provider."""

from __future__ import annotations

import re
from typing import Protocol

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


def get_llm_provider(name: str) -> LLMProvider:
    if name == "extractive":
        return ExtractiveLLMProvider()
    raise ValueError(f"unsupported LLM provider: {name}")
