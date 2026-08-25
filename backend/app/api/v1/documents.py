"""Document upload, inspection, versioning, and deletion."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from app.api.v1.deps import AuthenticatedPrincipal, get_ingestion_service, require_permission
from app.api.v1.enqueue import enqueue_outcome
from app.auth.rbac import Permission
from app.core.bootstrap import DEV_UPLOAD_SOURCE_ID
from app.ingestion.errors import IngestionError, NotFoundError
from app.ingestion.mime import UnsupportedUpload
from app.ingestion.schemas import (
    BlockRead,
    ChunkRead,
    ChunksRead,
    DocumentRead,
    DocumentVersionRead,
    DuplicateRead,
    JobRead,
    ParsedBlocksRead,
    UploadResult,
)
from app.ingestion.service import IngestionService
from app.retrieval.acl import can_read_document

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("", response_model=list[DocumentRead])
def list_documents(
    principal: Annotated[AuthenticatedPrincipal, Depends(require_permission(Permission.READ))],
    service: Annotated[IngestionService, Depends(get_ingestion_service)],
    source_id: UUID | None = None,
    state: str | None = None,
) -> list[DocumentRead]:
    docs = service.list_documents(
        principal.organization.id,
        source_connection_id=source_id,
        state=state,
    )
    docs = [doc for doc in docs if can_read_document(doc.permissions or {}, principal.acl)]
    return [DocumentRead.model_validate(item) for item in docs]


@router.post("/upload", response_model=UploadResult)
async def upload_document(
    principal: Annotated[AuthenticatedPrincipal, Depends(require_permission(Permission.WRITE))],
    service: Annotated[IngestionService, Depends(get_ingestion_service)],
    file: Annotated[UploadFile, File()],
    source_connection_id: Annotated[UUID | None, Form()] = None,
    source_id: Annotated[str | None, Form()] = None,
) -> UploadResult:
    payload = await file.read()
    try:
        outcome = service.submit_upload(
            organization_id=principal.organization.id,
            source_connection_id=source_connection_id or DEV_UPLOAD_SOURCE_ID,
            filename=file.filename or "upload.bin",
            data=payload,
            declared_mime=file.content_type,
            source_id=source_id,
        )
    except UnsupportedUpload as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except IngestionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    enqueue_outcome(service.session, outcome)
    return UploadResult(
        unchanged=outcome.unchanged,
        document=DocumentRead.model_validate(outcome.document),
        job=JobRead.model_validate(outcome.job),
    )


@router.get("/{document_id}", response_model=DocumentRead)
def get_document(
    document_id: UUID,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_permission(Permission.READ))],
    service: Annotated[IngestionService, Depends(get_ingestion_service)],
) -> DocumentRead:
    try:
        document = service.get_document(principal.organization.id, document_id)
        if not can_read_document(document.permissions or {}, principal.acl):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="document forbidden")
        return DocumentRead.model_validate(document)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/{document_id}/versions", response_model=list[DocumentVersionRead])
def list_document_versions(
    document_id: UUID,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_permission(Permission.READ))],
    service: Annotated[IngestionService, Depends(get_ingestion_service)],
) -> list[DocumentVersionRead]:
    try:
        document = service.get_document(principal.organization.id, document_id)
        if not can_read_document(document.permissions or {}, principal.acl):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="document forbidden")
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return [DocumentVersionRead.model_validate(item) for item in document.versions]


@router.get("/{document_id}/blocks", response_model=ParsedBlocksRead)
def get_document_blocks(
    document_id: UUID,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_permission(Permission.READ))],
    service: Annotated[IngestionService, Depends(get_ingestion_service)],
    version: int | None = None,
) -> ParsedBlocksRead:
    try:
        document, doc_version, blocks = service.get_parsed_blocks(
            principal.organization.id,
            document_id,
            version_number=version,
        )
        if not can_read_document(document.permissions or {}, principal.acl):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="document forbidden")
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return ParsedBlocksRead(
        document_id=document.id,
        version_id=doc_version.id,
        version_number=doc_version.version_number,
        parser_name=doc_version.parser_name,
        parser_version=doc_version.parser_version,
        used_ocr=doc_version.used_ocr,
        title=document.title,
        language=doc_version.language,
        normalized_content_hash=doc_version.normalized_content_hash,
        warnings=list(doc_version.parse_warnings or []),
        blocks=[
            BlockRead(
                id=item.id,
                ordinal=item.ordinal,
                type=item.block_type,
                text=item.text,
                normalized_text=item.normalized_text,
                dropped=bool((item.extra or {}).get("dropped")),
                drop_reason=(item.extra or {}).get("drop_reason"),
                level=item.heading_level,
                page=item.page,
                section=item.section,
                metadata=item.extra or {},
            )
            for item in blocks
        ],
    )


@router.get("/{document_id}/duplicates", response_model=list[DuplicateRead])
def list_document_duplicates(
    document_id: UUID,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_permission(Permission.READ))],
    service: Annotated[IngestionService, Depends(get_ingestion_service)],
) -> list[DuplicateRead]:
    try:
        document = service.get_document(principal.organization.id, document_id)
        if not can_read_document(document.permissions or {}, principal.acl):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="document forbidden")
        rows = service.list_duplicates(principal.organization.id, document_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return [DuplicateRead.model_validate(item) for item in rows]



@router.get("/{document_id}/chunks", response_model=ChunksRead)
def get_document_chunks(
    document_id: UUID,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_permission(Permission.READ))],
    service: Annotated[IngestionService, Depends(get_ingestion_service)],
    version: int | None = None,
) -> ChunksRead:
    try:
        document, doc_version, chunks = service.get_chunks(
            principal.organization.id,
            document_id,
            version_number=version,
        )
        if not can_read_document(document.permissions or {}, principal.acl):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="document forbidden")
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return ChunksRead(
        document_id=document.id,
        version_id=doc_version.id,
        version_number=doc_version.version_number,
        strategy=doc_version.chunk_strategy,
        chunker_version=doc_version.chunker_version,
        chunk_count=doc_version.chunk_count,
        chunks=[
            ChunkRead(
                id=item.id,
                ordinal=item.ordinal,
                text=item.text,
                token_count=item.token_count,
                page=item.page,
                section=item.section,
                strategy=item.strategy,
                kind=item.kind,
                parent_chunk_id=item.parent_chunk_id,
                metadata=item.extra or {},
            )
            for item in chunks
        ],
    )

@router.post("/{document_id}/reprocess", response_model=UploadResult)
def reprocess_document(
    document_id: UUID,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_permission(Permission.WRITE))],
    service: Annotated[IngestionService, Depends(get_ingestion_service)],
) -> UploadResult:
    try:
        document = service.get_document(principal.organization.id, document_id)
        if not can_read_document(document.permissions or {}, principal.acl):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="document forbidden")
        outcome = service.reprocess(principal.organization.id, document.id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    enqueue_outcome(service.session, outcome)
    return UploadResult(
        unchanged=outcome.unchanged,
        document=DocumentRead.model_validate(outcome.document),
        job=JobRead.model_validate(outcome.job),
    )


@router.delete("/{document_id}", response_model=DocumentRead)
def delete_document(
    document_id: UUID,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_permission(Permission.WRITE))],
    service: Annotated[IngestionService, Depends(get_ingestion_service)],
) -> DocumentRead:
    try:
        document = service.get_document(principal.organization.id, document_id)
        if not can_read_document(document.permissions or {}, principal.acl):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="document forbidden")
        document = service.delete_document(principal.organization.id, document_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    from app.workers.embedding import delete_document_vectors

    delete_document_vectors.delay(str(document.id))
    return DocumentRead.model_validate(document)
