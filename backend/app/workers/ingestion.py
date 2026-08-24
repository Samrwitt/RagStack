"""Celery task that drives fetch / hash / version for a queued job."""

from typing import Any
from uuid import UUID

from app.core.db import get_sync_session_factory
from app.core.logging import get_logger
from app.ingestion.errors import NotFoundError
from app.ingestion.service import IngestionService
from app.workers.celery_app import celery_app

logger = get_logger(__name__)


@celery_app.task(name="app.workers.ingestion.process_ingestion_job", bind=True, max_retries=3)
def process_ingestion_job(self: Any, job_id: str) -> dict[str, str | bool | int]:
    factory = get_sync_session_factory()
    with factory() as session:
        service = IngestionService(session)
        try:
            outcome = service.process_job(UUID(job_id))
            session.commit()
        except NotFoundError:
            session.commit()
            logger.exception("ingestion.job_permanent_failure", job_id=job_id)
            raise
        except Exception as exc:
            session.commit()
            logger.exception("ingestion.job_failed", job_id=job_id)
            raise self.retry(exc=exc, countdown=min(2**self.request.retries, 30)) from exc

    return {
        "job_id": str(outcome.job.id),
        "document_id": str(outcome.document.id),
        "status": outcome.job.status,
        "unchanged": outcome.unchanged,
        "version": outcome.document.current_version,
    }
