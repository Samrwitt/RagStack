"""Grounded RAG chat endpoint."""

from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.v1.deps import AuthenticatedPrincipal, get_sync_session, require_permission
from app.auth.rbac import Permission
from app.generation.models import ChatMessage
from app.generation.schemas import ChatRequest, ChatResponse, CitationRead
from app.generation.service import GenerationService
from app.retrieval.models import RetrievalFilters, RetrievalMode

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
def chat(
    payload: ChatRequest,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_permission(Permission.READ))],
    session: Annotated[Session, Depends(get_sync_session)],
) -> ChatResponse:
    try:
        answer = GenerationService(session).answer(
            question=payload.question,
            history=[
                ChatMessage(role=item.role, content=item.content)
                for item in payload.history
            ],
            filters=RetrievalFilters(
                organization_id=principal.organization.id,
                workspace_id=payload.workspace_id,
                source_connection_id=payload.source_connection_id,
                source_type=payload.source_type,
                document_ids=tuple(payload.document_ids),
                language=payload.language,
            ),
            mode=RetrievalMode(payload.mode),
            top_k=payload.top_k,
            candidate_k=payload.candidate_k,
            rerank=True,
            acl=principal.acl,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return ChatResponse(
        answer=answer.answer,
        evidence_status=answer.evidence_status,
        citations=[CitationRead(**asdict(item)) for item in answer.citations],
        retrieval_query=answer.retrieval_query,
        context=[asdict(item) for item in answer.context],
    )
