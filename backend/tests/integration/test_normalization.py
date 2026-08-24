"""Exact duplicates are recorded; related documents are not deleted."""

from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.core.db import get_sync_session_factory
from app.ingestion.service import IngestionService
from app.models.duplicate import DocumentDuplicate
from app.models.enums import DocumentState, DuplicateKind, SourceStatus, SourceType
from app.models.organization import Organization, Workspace
from app.models.source import SourceConnection
from tests.integration.services import requires_minio, requires_postgres

pytestmark = [pytest.mark.integration, requires_postgres, requires_minio]

_POLICY = (
    b"Employees receive 22 days annual leave each calendar year.\n"
    b"Requests must go through HR before travel is booked.\n"
)


@pytest.fixture
def session() -> Session:
    factory = get_sync_session_factory()
    db = factory()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _tenant(session: Session) -> tuple[Organization, Workspace, SourceConnection]:
    org = Organization(name="Dedupe Test", slug=f"dedupe-{uuid4().hex[:10]}")
    session.add(org)
    session.flush()
    workspace = Workspace(organization_id=org.id, name="Knowledge", slug="knowledge")
    session.add(workspace)
    session.flush()
    source = SourceConnection(
        organization_id=org.id,
        workspace_id=workspace.id,
        name="Uploads",
        source_type=SourceType.FILE_UPLOAD.value,
        status=SourceStatus.CONNECTED.value,
        config={},
        checkpoint={},
    )
    session.add(source)
    session.flush()
    return org, workspace, source


def _finish(service: IngestionService, session: Session, outcome):  # noqa: ANN001
    session.commit()
    if outcome.enqueue:
        processed = service.process_job(outcome.job.id)
        session.commit()
        return processed
    session.refresh(outcome.document)
    session.refresh(outcome.job)
    return outcome


def test_same_bytes_different_filenames_are_exact_duplicates(session: Session) -> None:
    org, _workspace, source = _tenant(session)
    service = IngestionService(session)
    first = _finish(
        service,
        session,
        service.submit_upload(
            organization_id=org.id,
            source_connection_id=source.id,
            filename="handbook.txt",
            data=_POLICY,
            declared_mime="text/plain",
        ),
    )
    second = _finish(
        service,
        session,
        service.submit_upload(
            organization_id=org.id,
            source_connection_id=source.id,
            filename="leave-policy.txt",
            data=_POLICY,
            declared_mime="text/plain",
        ),
    )
    assert first.document.id != second.document.id
    assert first.document.current_state == DocumentState.NORMALIZED.value
    assert second.document.current_state == DocumentState.NORMALIZED.value
    assert first.document.current_state != DocumentState.DELETED.value
    session.refresh(second.document)
    assert second.document.canonical_document_id == first.document.id
    rows = (
        session.query(DocumentDuplicate)
        .filter_by(organization_id=org.id, kind=DuplicateKind.EXACT.value)
        .all()
    )
    assert len(rows) == 1
    assert rows[0].canonical_document_id == first.document.id
    assert rows[0].duplicate_document_id == second.document.id
    listed = service.list_duplicates(org.id, second.document.id)
    assert len(listed) == 1
    assert listed[0].score == 1.0
