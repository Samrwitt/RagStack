"""Request-scoped dependencies for tenant context and the ingestion service."""

from collections.abc import Generator
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.bootstrap import default_organization_id, ensure_dev_tenant
from app.core.config import get_settings
from app.core.db import get_sync_session_factory
from app.ingestion.service import IngestionService
from app.models.organization import Organization


def get_sync_session() -> Generator[Session, None, None]:
    factory = get_sync_session_factory()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_current_organization(
    session: Annotated[Session, Depends(get_sync_session)],
    x_organization_id: Annotated[str | None, Header()] = None,
) -> Organization:
    settings = get_settings()
    if x_organization_id:
        try:
            org_id = UUID(x_organization_id)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="invalid X-Organization-Id",
            ) from exc
    elif settings.app_env in {"development", "test"}:
        org_id = default_organization_id()
        ensure_dev_tenant(session)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Organization-Id header is required",
        )
    org = session.get(Organization, org_id)
    if org is None:
        if settings.app_env in {"development", "test"}:
            return ensure_dev_tenant(session)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="organization not found")
    return org


def get_ingestion_service(
    session: Annotated[Session, Depends(get_sync_session)],
) -> IngestionService:
    return IngestionService(session)
