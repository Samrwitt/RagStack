"""RAG evaluation: retrieval metrics, groundedness, and experiment comparison."""

from app.evaluation.metrics import mrr, ndcg_at_k, precision_at_k, recall_at_k
from app.evaluation.service import EvaluationService

__all__ = ["EvaluationService", "mrr", "ndcg_at_k", "precision_at_k", "recall_at_k"]
