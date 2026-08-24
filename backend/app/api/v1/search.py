"""Retrieval endpoints."""

from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_organization, get_sync_session
from app.models.organization import Organization
from app.retrieval.models import ACLContext, RetrievalFilters, RetrievalMode, RetrievalRequest
from app.retrieval.schemas import SearchHitRead, SearchRequest, SearchResponse
from app.retrieval.service import RetrievalService

router = APIRouter(prefix="/search", tags=["search"])


@router.post("", response_model=SearchResponse)
def search(
    payload: SearchRequest,
    org: Annotated[Organization, Depends(get_current_organization)],
    session: Annotated[Session, Depends(get_sync_session)],
) -> SearchResponse:
    request = RetrievalRequest(
        query=payload.query,
        mode=RetrievalMode(payload.mode),
        top_k=payload.top_k,
        candidate_k=payload.candidate_k,
        filters=RetrievalFilters(
            organization_id=org.id,
            workspace_id=payload.workspace_id,
            source_connection_id=payload.source_connection_id,
            source_type=payload.source_type,
            document_ids=tuple(payload.document_ids),
            language=payload.language,
        ),
        acl=ACLContext(
            user_id=payload.user_id,
            group_ids=frozenset(payload.group_ids),
        ),
        rerank=payload.rerank,
        context_token_budget=payload.context_token_budget,
    )
    try:
        hits, context = RetrievalService(session).search_with_context(request)
    except NotImplementedError as exc:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return SearchResponse(
        query=payload.query,
        mode=payload.mode,
        hits=[SearchHitRead(**asdict(hit)) for hit in hits],
        context=[SearchHitRead(**asdict(item.hit)) for item in context],
    )
