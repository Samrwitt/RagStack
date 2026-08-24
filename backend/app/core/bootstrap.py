"""Idempotent development tenant.

Phase 13 replaces this with authenticated org creation. Local Compose and
tests need a stable organization/workspace/upload source without a UI.
"""

from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.enums import SourceStatus, SourceType
from app.models.organization import Organization, Workspace
from app.models.source import SourceConnection

logger = get_logger(__name__)

DEV_ORGANIZATION_ID = UUID("aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeee1")
DEV_WORKSPACE_ID = UUID("aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeee2")
DEV_UPLOAD_SOURCE_ID = UUID("aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeee3")
DEV_ORGANIZATION_SLUG = "acme"
DEV_WORKSPACE_SLUG = "knowledge"


def ensure_dev_tenant(session: Session) -> Organization:
    """Create the Acme Systems tenant if it does not exist."""
    org = session.get(Organization, DEV_ORGANIZATION_ID)
    if org is None:
        org = Organization(
            id=DEV_ORGANIZATION_ID,
            name="Acme Systems",
            slug=DEV_ORGANIZATION_SLUG,
        )
        session.add(org)
        logger.info("bootstrap.organization", organization_id=str(org.id))

    workspace = session.get(Workspace, DEV_WORKSPACE_ID)
    if workspace is None:
        workspace = Workspace(
            id=DEV_WORKSPACE_ID,
            organization_id=DEV_ORGANIZATION_ID,
            name="Knowledge",
            slug=DEV_WORKSPACE_SLUG,
        )
        session.add(workspace)
        logger.info("bootstrap.workspace", workspace_id=str(workspace.id))

    source = session.get(SourceConnection, DEV_UPLOAD_SOURCE_ID)
    if source is None:
        source = SourceConnection(
            id=DEV_UPLOAD_SOURCE_ID,
            organization_id=DEV_ORGANIZATION_ID,
            workspace_id=DEV_WORKSPACE_ID,
            name="Local uploads",
            source_type=SourceType.FILE_UPLOAD.value,
            status=SourceStatus.CONNECTED.value,
            config={},
            checkpoint={},
        )
        session.add(source)
        logger.info("bootstrap.source", source_id=str(source.id))

    session.flush()
    return org


def default_organization_id() -> UUID:
    configured = get_settings().default_organization_id
    return UUID(configured)
