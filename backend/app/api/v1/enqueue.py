"""Enqueue ingestion work only after the control-plane row is committed."""

from sqlalchemy.orm import Session

from app.ingestion.service import IngestOutcome


def enqueue_outcome(session: Session, outcome: IngestOutcome) -> None:
    if not outcome.enqueue:
        return
    from app.workers.ingestion import process_ingestion_job

    session.commit()
    result = process_ingestion_job.delay(str(outcome.job.id))
    outcome.job.celery_task_id = result.id
    session.add(outcome.job)
    session.commit()
