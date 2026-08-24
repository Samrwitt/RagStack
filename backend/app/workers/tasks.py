"""Celery tasks.

Ingestion, embedding, and indexing tasks are added in later phases. Keep
task names stable; they are part of the worker contract.
"""

from app.workers.celery_app import celery_app


@celery_app.task(name="app.workers.tasks.ping")
def ping() -> str:
    """Liveness probe used by health checks and integration tests."""
    return "pong"
