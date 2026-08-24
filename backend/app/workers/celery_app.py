"""Celery application.

Queues are split by workload so ingestion, embedding, and indexing can be
scaled independently. Phase 1 only registers a ping task to prove the
broker/result-backend path.
"""

from celery import Celery
from kombu import Queue

from app.core.config import get_settings


def create_celery() -> Celery:
    settings = get_settings()
    app = Celery(
        "corpusforge",
        broker=settings.celery_broker_url,
        backend=settings.celery_result_backend,
        include=[
            "app.workers.tasks",
            "app.workers.ingestion",
            "app.workers.embedding",
            "app.workers.connectors",
        ],
    )
    app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,
        task_track_started=True,
        task_acks_late=True,
        worker_prefetch_multiplier=1,
        worker_concurrency=settings.celery_worker_concurrency,
        task_default_queue="default",
        task_queues=(
            Queue("default"),
            Queue("ingestion"),
            Queue("embedding"),
            Queue("indexing"),
        ),
        task_routes={
            "app.workers.tasks.ping": {"queue": "default"},
            "app.workers.ingestion.process_ingestion_job": {"queue": "ingestion"},
            "app.workers.embedding.embed_document": {"queue": "embedding"},
            "app.workers.connectors.sync_source": {"queue": "ingestion"},
        },
        broker_connection_retry_on_startup=True,
        result_expires=3600,
    )
    return app


celery_app = create_celery()
