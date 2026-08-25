"""Request-scoped dependencies for tenant context and the ingestion service."""

from collections.abc import Generator
from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.auth.rbac import Permission, can
from app.core.bootstrap import DEV_USER_EMAIL, default_organization_id, ensure_dev_tenant
from app.core.config import get_settings
from app.core.db import get_sync_session_factory
from app.core.security import decode_access_token
from app.ingestion.service import IngestionService
from app.models.organization import Organization, OrganizationMembership, User
from app.retrieval.models import ACLContext


@dataclass(frozen=True, slots=True)
class AuthenticatedPrincipal:
    user: User
    organization: Organization
    membership: OrganizationMembership

    @property
    def role(self) -> str:
        return self.membership.role

    @property
    def group_ids(self) -> frozenset[str]:
        groups = {str(item) for item in (self.user.groups or [])}
        groups.add(f"role:{self.role.lower()}")
        groups.add(f"org:{self.organization.id}")
        groups.add(f"email:{self.user.email.lower()}")
        return frozenset(groups)

    @property
    def acl(self) -> ACLContext:
        return ACLContext(
            user_id=str(self.user.id),
            user_email=self.user.email.lower(),
            group_ids=self.group_ids,
        )


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


def get_current_principal(
    session: Annotated[Session, Depends(get_sync_session)],
    authorization: Annotated[str | None, Header()] = None,
) -> AuthenticatedPrincipal:
    settings = get_settings()
    ensure_dev_tenant(session) if settings.app_env in {"development", "test"} else None
    if authorization:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="invalid auth header",
            )
        try:
            claims = decode_access_token(token, secret_key=settings.secret_key)
            user_id = UUID(str(claims["sub"]))
            org_id = UUID(str(claims["org"]))
        except (KeyError, TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="invalid token",
            ) from exc
    elif settings.app_env in {"development", "test"}:
        org_id = default_organization_id()
        user = session.scalars(select(User).where(User.email == DEV_USER_EMAIL)).first()
        if user is None:
            ensure_dev_tenant(session)
            user = session.scalars(select(User).where(User.email == DEV_USER_EMAIL)).one()
        user_id = user.id
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization bearer token is required",
        )
    principal = _load_principal(session, user_id=user_id, organization_id=org_id)
    if principal is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="membership required")
    if not principal.user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user is disabled")
    return principal


def get_current_organization(
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
) -> Organization:
    return principal.organization


def require_permission(permission: Permission):
    def dependency(
        principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    ) -> AuthenticatedPrincipal:
        if not can(principal.role, permission):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="insufficient role")
        return principal

    return dependency


def _load_principal(
    session: Session,
    *,
    user_id: UUID,
    organization_id: UUID,
) -> AuthenticatedPrincipal | None:
    membership = session.scalars(
        select(OrganizationMembership)
        .options(
            selectinload(OrganizationMembership.user),
            selectinload(OrganizationMembership.organization),
        )
        .where(
            OrganizationMembership.user_id == user_id,
            OrganizationMembership.organization_id == organization_id,
        )
    ).first()
    if membership is None:
        return None
    return AuthenticatedPrincipal(
        user=membership.user,
        organization=membership.organization,
        membership=membership,
    )


def get_ingestion_service(
    session: Annotated[Session, Depends(get_sync_session)],
) -> IngestionService:
    return IngestionService(session)
