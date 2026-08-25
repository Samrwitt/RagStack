"""JWT authentication endpoints."""

from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.deps import AuthenticatedPrincipal, get_current_principal, get_sync_session
from app.auth.schemas import CurrentUserRead, LoginRequest, TokenResponse
from app.core.config import get_settings
from app.core.security import create_access_token, verify_password
from app.models.organization import OrganizationMembership, User

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest,
    session: Annotated[Session, Depends(get_sync_session)],
) -> TokenResponse:
    settings = get_settings()
    user = session.scalars(select(User).where(User.email == payload.email.lower())).first()
    if (
        user is None
        or not user.is_active
        or not verify_password(payload.password, user.hashed_password)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid email or password",
        )
    membership = session.scalars(
        select(OrganizationMembership).where(OrganizationMembership.user_id == user.id)
    ).first()
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="user has no organization membership",
        )
    expires = timedelta(minutes=settings.access_token_expire_minutes)
    return TokenResponse(
        access_token=create_access_token(
            subject=str(user.id),
            organization_id=str(membership.organization_id),
            secret_key=settings.secret_key,
            expires_delta=expires,
        ),
        expires_in=int(expires.total_seconds()),
    )


@router.get("/me", response_model=CurrentUserRead)
def me(
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
) -> CurrentUserRead:
    return CurrentUserRead(
        id=str(principal.user.id),
        email=principal.user.email,
        display_name=principal.user.display_name,
        organization_id=str(principal.organization.id),
        role=principal.role,
        groups=sorted(principal.group_ids),
    )
