import pytest

from app.evaluation.metrics import (
    citation_completeness,
    citation_correctness,
    groundedness,
    mrr,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
)


def test_retrieval_metrics() -> None:
    retrieved = ["a", "b", "c"]
    relevant = {"b", "d"}

    assert recall_at_k(retrieved, relevant, 2) == 0.5
    assert precision_at_k(retrieved, relevant, 2) == 0.5
    assert mrr(retrieved, relevant) == 0.5
    assert ndcg_at_k(retrieved, relevant, 3) == pytest.approx(0.38685, rel=1e-4)


def test_answer_metrics() -> None:
    relevant = {"doc-1", "doc-2"}

    assert citation_correctness(["doc-1", "doc-3"], relevant) == 0.5
    assert citation_completeness(["doc-1", "doc-3"], relevant) == 0.5
    assert groundedness("annual leave days", ["annual leave days are 22"]) == 1.0
