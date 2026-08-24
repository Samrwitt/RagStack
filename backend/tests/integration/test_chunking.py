"""Ingestion continues through CHUNKING after normalization."""

from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.core.db import get_sync_session_factory
from app.ingestion.service import IngestionService
from app.models.chunk import DocumentChunk
from app.models.document import DocumentVersion
from app.models.enums import DocumentState, SourceStatus, SourceType
from app.models.organization import Organization, Workspace
from app.models.source import SourceConnection
from tests.integration.services import requires_minio, requires_postgres

pytestmark = [pytest.mark.integration, requires_postgres, requires_minio]

_MARKDOWN = b"""# Employee Handbook

## Leave policy

Employees receive 22 days annual leave each calendar year.
Requests must go through HR before travel is booked.
Carry-over is capped at five days with manager approval.

## Remote work

Employees may work remotely two days each week when their role allows it.
"""


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
    org = Organization(name="Chunk Test", slug=f"chunk-{uuid4().hex[:10]}")
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


def test_upload_produces_parent_child_chunks(session: Session) -> None:
    org, _workspace, source = _tenant(session)
    service = IngestionService(session)
    outcome = _finish(
        service,
        session,
        service.submit_upload(
            organization_id=org.id,
            source_connection_id=source.id,
            filename="handbook.md",
            data=_MARKDOWN,
            declared_mime="text/markdown",
        ),
    )
    assert outcome.document.current_state == DocumentState.CHUNKED.value
    version = (
        session.query(DocumentVersion)
        .filter_by(document_id=outcome.document.id, is_current=True)
        .one()
    )
    assert version.chunk_strategy == "parent_child"
    assert version.chunk_count >= 2
    assert version.chunked_at is not None
    chunks = (
        session.query(DocumentChunk)
        .filter_by(version_id=version.id)
        .order_by(DocumentChunk.ordinal)
        .all()
    )
    assert chunks
    parents = [c for c in chunks if c.kind == "parent"]
    children = [c for c in chunks if c.kind == "child"]
    assert parents
    assert any(c.section for c in chunks)
    if children:
        assert all(c.parent_chunk_id is not None for c in children)
    document, chunk_version, listed = service.get_chunks(org.id, outcome.document.id)
    assert chunk_version.id == version.id
    assert len(listed) == len(chunks)
    assert document.id == outcome.document.id
