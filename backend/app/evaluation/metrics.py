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
    if not answer.strip() or not context_texts:
        return 0.0
    answer_terms = [t for t in answer.lower().split() if len(t) > 2]
    if not answer_terms:
        return 0.0
    context_blob = " ".join(context_texts).lower()
    context_terms = set(context_blob.split())
    matched_unigrams = sum(1 for term in answer_terms if term in context_terms)
    
    # Bi-gram overlap check
    answer_bigrams = [
        f"{answer_terms[i]} {answer_terms[i+1]}"
        for i in range(len(answer_terms) - 1)
    ]
    if answer_bigrams:
        matched_bigrams = sum(1 for bg in answer_bigrams if bg in context_blob)
        return (0.5 * (matched_unigrams / len(answer_terms))) + (0.5 * (matched_bigrams / len(answer_bigrams)))
    return matched_unigrams / len(answer_terms)


def faithfulness(answer: str, context_texts: list[str]) -> float:
    """Calculates ratio of answer sentences whose core claims are supported by context."""
    if not answer.strip() or not context_texts:
        return 0.0
    context_blob = " ".join(context_texts).lower()
    sentences = [s.strip() for s in answer.replace("\n", ". ").split(".") if s.strip()]
    if not sentences:
        return 0.0
    
    stop_words = {"the", "a", "an", "in", "on", "of", "to", "is", "are", "and", "or", "for", "with", "that", "this", "it", "by", "as", "at", "be"}
    supported = 0
    for sentence in sentences:
        words = [w.lower().strip(".,!?;:") for w in sentence.split()]
        content_words = [w for w in words if w not in stop_words and len(w) > 2]
        if not content_words:
            supported += 1
            continue
        matches = sum(1 for w in content_words if w in context_blob)
        if (matches / len(content_words)) >= 0.5:
            supported += 1
            
    return supported / len(sentences)


def answer_relevance(answer: str, question: str, expected_answer: str = "") -> float:
    """Calculates answer relevance against question keywords and optional ground truth expected answer."""
    if not answer.strip() or not question.strip():
        return 0.0
    stop_words = {"what", "how", "why", "who", "where", "when", "is", "are", "the", "a", "an", "in", "of", "to", "for", "do", "does"}
    q_words = set(w.lower().strip("?,!.") for w in question.split() if w.lower() not in stop_words)
    a_blob = answer.lower()
    
    q_coverage = (sum(1 for qw in q_words if qw in a_blob) / len(q_words)) if q_words else 1.0
    
    if expected_answer and expected_answer.strip():
        exp_words = set(w.lower().strip(".,!?:") for w in expected_answer.split() if w.lower() not in stop_words)
        a_words = set(w.lower().strip(".,!?:") for w in answer.split() if w.lower() not in stop_words)
        if exp_words:
            exp_overlap = len(a_words.intersection(exp_words)) / len(exp_words)
            return 0.4 * q_coverage + 0.6 * exp_overlap
            
    return q_coverage


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0
