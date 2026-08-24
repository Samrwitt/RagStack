"""Retrieval and answer evaluation metrics."""

from __future__ import annotations

import math


def recall_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    if not relevant:
        return 0.0
    return len(set(retrieved[:k]).intersection(relevant)) / len(relevant)


def precision_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    if k <= 0:
        return 0.0
    return len(set(retrieved[:k]).intersection(relevant)) / k


def mrr(retrieved: list[str], relevant: set[str]) -> float:
    for index, document_id in enumerate(retrieved, start=1):
        if document_id in relevant:
            return 1.0 / index
    return 0.0


def ndcg_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    dcg = 0.0
    for index, document_id in enumerate(retrieved[:k], start=1):
        if document_id in relevant:
            dcg += 1.0 / math.log2(index + 1)
    ideal_hits = min(len(relevant), k)
    if ideal_hits == 0:
        return 0.0
    ideal = sum(1.0 / math.log2(index + 1) for index in range(1, ideal_hits + 1))
    return dcg / ideal


def citation_correctness(cited: list[str], relevant: set[str]) -> float:
    if not cited:
        return 0.0
    return len(set(cited).intersection(relevant)) / len(set(cited))


def citation_completeness(cited: list[str], relevant: set[str]) -> float:
    if not relevant:
        return 0.0
    return len(set(cited).intersection(relevant)) / len(relevant)


def groundedness(answer: str, context_texts: list[str]) -> float:
    answer_terms = set(answer.lower().split())
    if not answer_terms:
        return 0.0
    context_terms = set(" ".join(context_texts).lower().split())
    return len(answer_terms.intersection(context_terms)) / len(answer_terms)


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0
