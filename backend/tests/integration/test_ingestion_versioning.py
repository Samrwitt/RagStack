"""Acceptance: unchanged uploads skip work; changed content versions."""

from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.core.db import get_sync_session_factory
from app.ingestion.hashing import sha256_digest
from app.ingestion.identity import stable_document_id
from app.ingestion.service import IngestionService
from app.models.block import DocumentBlock
from app.models.document import DocumentVersion
from app.models.enums import DocumentState, JobStatus, SourceStatus, SourceType
from app.models.organization import Organization, Workspace
from app.models.source import SourceConnection
from tests.integration.services import requires_minio, requires_postgres

pytestmark = [pytest.mark.integration, requires_postgres, requires_minio]


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
    org = Organization(name="Acme Test", slug=f"acme-{uuid4().hex[:10]}")
    session.add(org)
    session.flush()
    workspace = Workspace(
        organization_id=org.id,
        name="Knowledge",
        slug="knowledge",
    )
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


def test_unchanged_upload_does_not_reprocess(session: Session) -> None:
    org, _workspace, source = _tenant(session)
    service = IngestionService(session)
    payload = b"Employees receive 22 days annual leave.\n"

    first = _finish(
        service,
        session,
        service.submit_upload(
            organization_id=org.id,
            source_connection_id=source.id,
            filename="employee-handbook.txt",
            data=payload,
            declared_mime="text/plain",
        ),
    )
    assert first.unchanged is False
    assert first.document.current_version == 1
    assert first.document.current_state == DocumentState.NORMALIZED.value
    assert first.document.content_hash == sha256_digest(payload)
    assert first.job.status == JobStatus.SUCCEEDED.value
    blocks = session.query(DocumentBlock).filter_by(document_id=first.document.id).all()
    assert len(blocks) >= 2
    assert any(block.block_type == "paragraph" for block in blocks)

    second = _finish(
        service,
        session,
        service.submit_upload(
            organization_id=org.id,
            source_connection_id=source.id,
            filename="employee-handbook.txt",
            data=payload,
            declared_mime="text/plain",
        ),
    )
    assert second.unchanged is True
    assert second.document.id == first.document.id
    assert second.document.current_version == 1
    assert second.job.status == JobStatus.SKIPPED_UNCHANGED.value
    versions = session.query(DocumentVersion).filter_by(document_id=first.document.id).all()
    assert len(versions) == 1


def test_changed_upload_creates_new_version(session: Session) -> None:
    org, _workspace, source = _tenant(session)
    service = IngestionService(session)

    first = _finish(
        service,
        session,
        service.submit_upload(
            organization_id=org.id,
            source_connection_id=source.id,
            filename="employee-handbook.txt",
            data=b"Employees receive 18 days annual leave.\n",
            declared_mime="text/plain",
        ),
    )
    second = _finish(
        service,
        session,
        service.submit_upload(
            organization_id=org.id,
            source_connection_id=source.id,
            filename="employee-handbook.txt",
            data=b"Employees receive 22 days annual leave.\n",
            declared_mime="text/plain",
        ),
    )
    assert second.document.id == first.document.id
    assert second.document.current_version == 2
    assert second.unchanged is False
    versions = (
        session.query(DocumentVersion)
        .filter_by(document_id=first.document.id)
        .order_by(DocumentVersion.version_number)
        .all()
    )
    assert [item.version_number for item in versions] == [1, 2]
    assert versions[0].is_current is False
    assert versions[1].is_current is True
    assert versions[0].content_hash != versions[1].content_hash
    assert second.document.current_state == DocumentState.NORMALIZED.value
    current_blocks = (
        session.query(DocumentBlock).filter_by(version_id=versions[1].id).all()
    )
    assert any("22 days" in block.text for block in current_blocks)


def test_same_filename_different_orgs_are_distinct(session: Session) -> None:
    org_a, _, source_a = _tenant(session)
    org_b, _, source_b = _tenant(session)
    assert stable_document_id(org_a.id, "file_upload", source_a.id, "handbook.txt") != (
        stable_document_id(org_b.id, "file_upload", source_b.id, "handbook.txt")
    )
