"""Celery tasks for source connector sync."""

import asyncio
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from app.connectors.sync import ConnectorSyncService
from app.core.db import get_sync_session_factory
from app.core.logging import get_logger
from app.ingestion.errors import NotFoundError
from app.models.enums import JobStatus
from app.models.job import IngestionJob
from app.workers.celery_app import celery_app

logger = get_logger(__name__)


@celery_app.task(name="app.workers.connectors.sync_source", bind=True, max_retries=3)
def sync_source(self: Any, job_id: str) -> dict[str, str | int]:
    factory = get_sync_session_factory()
    with factory() as session:
        job = session.get(IngestionJob, UUID(job_id))
        if job is None:
            raise NotFoundError(f"sync job {job_id} not found")
        job.status = JobStatus.RUNNING.value
        job.attempt += 1
        job.started_at = job.started_at or datetime.now(UTC)
        session.flush()
        try:
            if job.source_connection_id is None:
                raise NotFoundError("sync job has no source connection")
            service = ConnectorSyncService(session)
            outcome = asyncio.run(
                service.sync_source(
                    organization_id=job.organization_id,
                    source_connection_id=job.source_connection_id,
                )
            )
            job.status = JobStatus.SUCCEEDED.value
            job.stats = {
                "discovered": outcome.discovered,
                "fetched": outcome.fetched,
                "queued": outcome.queued,
                "skipped": outcome.skipped,
                "deleted": outcome.deleted,
                "checkpoint": outcome.checkpoint,
            }
            job.deterministic_key = None
            job.finished_at = datetime.now(UTC)
            session.commit()

            from app.workers.ingestion import process_ingestion_job

            for item in outcome.ingestion_jobs:
                if item.enqueue:
                    process_ingestion_job.delay(str(item.job.id))
        except Exception as exc:
            job.status = JobStatus.FAILED.value
            job.last_error = str(exc)
            job.deterministic_key = None
            job.finished_at = datetime.now(UTC)
            session.commit()
            logger.exception("connector.sync_failed", job_id=job_id)
            raise self.retry(exc=exc, countdown=min(2**self.request.retries, 30)) from exc

    return {
        "job_id": job_id,
        "discovered": int(job.stats.get("discovered", 0)),
        "queued": int(job.stats.get("queued", 0)),
    }
