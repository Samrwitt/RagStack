"""Parsing continues the ingestion job from FETCHED to PARSED."""

from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.core.db import get_sync_session_factory
from app.ingestion.service import IngestionService
from app.models.block import DocumentBlock
from app.models.document import DocumentVersion
from app.models.enums import DocumentState, JobStatus, JobType, SourceStatus, SourceType
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
    org = Organization(name="Parse Test", slug=f"parse-{uuid4().hex[:10]}")
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


def test_markdown_upload_parses_structured_blocks(session: Session) -> None:
    org, _workspace, source = _tenant(session)
    service = IngestionService(session)
    payload = b"""# Authentication

## Tokens

Use a bearer token.

- Access token
- Refresh token
"""
    outcome = _finish(
        service,
        session,
        service.submit_upload(
            organization_id=org.id,
            source_connection_id=source.id,
            filename="auth.md",
            data=payload,
            declared_mime="text/markdown",
        ),
    )
    assert outcome.document.current_state == DocumentState.PARSED.value
    assert outcome.document.title == "Authentication"
    version = (
        session.query(DocumentVersion)
        .filter_by(document_id=outcome.document.id, is_current=True)
        .one()
    )
    assert version.parser_name == "markdown"
    assert version.parser_version == 1
    assert version.used_ocr is False
    assert version.parsed_block_count >= 4
    types = {
        block.block_type
        for block in session.query(DocumentBlock).filter_by(version_id=version.id)
    }
    assert "title" in types
    assert "heading" in types
    assert "list" in types
    document, parsed_version, blocks = service.get_parsed_blocks(org.id, outcome.document.id)
    assert parsed_version.id == version.id
    assert blocks[0].block_type == "title"
    assert any(block.section == "Tokens" for block in blocks)


def test_reprocess_reparses_without_new_version(session: Session) -> None:
    org, _workspace, source = _tenant(session)
    service = IngestionService(session)
    first = _finish(
        service,
        session,
        service.submit_upload(
            organization_id=org.id,
            source_connection_id=source.id,
            filename="policy.txt",
            data=b"Original policy text.\n",
            declared_mime="text/plain",
        ),
    )
    reparsed = _finish(service, session, service.reprocess(org.id, first.document.id))
    assert reparsed.document.current_version == 1
    assert reparsed.document.current_state == DocumentState.PARSED.value
    assert reparsed.job.job_type == JobType.REPROCESS.value
    assert reparsed.job.status == JobStatus.SUCCEEDED.value
    assert reparsed.job.stats.get("reparsed") is True
    versions = session.query(DocumentVersion).filter_by(document_id=first.document.id).all()
    assert len(versions) == 1
