"""Ingestion control plane.

Owns source connections, canonical documents, versioning, hashing, jobs,
and FETCHED → … → NORMALIZED → CHUNKING → CHUNKED. Embedding starts in Phase 6.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import Select, delete, or_, select
from sqlalchemy.orm import Session, selectinload

from app.chunking.models import BlockInput
from app.chunking.registry import run_chunker
from app.connectors.protocol import FetchedContent
from app.core.config import get_settings
from app.core.storage import ObjectStorage, get_object_storage, raw_object_key
from app.ingestion.errors import NotFoundError, SourcePausedError, TenantMismatchError
from app.ingestion.hashing import sha256_digest
from app.ingestion.identity import normalize_source_id, stable_document_id
from app.ingestion.mime import validate_upload
from app.ingestion.state_machine import SUCCESS_STATES, transition
from app.models.block import DocumentBlock
from app.models.chunk import DocumentChunk
from app.models.document import Document, DocumentVersion
from app.models.duplicate import DocumentDuplicate
from app.models.enums import (
    DocumentState,
    FailureKind,
    JobStatus,
    JobType,
    SourceStatus,
    SourceType,
)
from app.models.job import IngestionJob
from app.models.organization import Organization, Workspace
from app.models.source import SourceConnection
from app.normalization.dedup import record_duplicates
from app.normalization.models import BlockSnapshot
from app.normalization.pipeline import normalize_blocks
from app.normalization.simhash import as_int64
from app.parsers.errors import PermanentParseError, UnsupportedMimeError
from app.parsers.models import RawDocument
from app.parsers.registry import get_parser_registry


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _original_filename(source_id: str, metadata: dict) -> str:
    name = metadata.get("original_filename") or Path(source_id).name or "original"
    return str(name)


@dataclass(slots=True)
class IngestOutcome:
    document: Document
    job: IngestionJob
    unchanged: bool
    enqueue: bool


class IngestionService:
    def __init__(self, session: Session, storage: ObjectStorage | None = None) -> None:
        self.session = session
        self.storage = storage or get_object_storage()

    def get_organization(self, organization_id: UUID) -> Organization:
        org = self.session.get(Organization, organization_id)
        if org is None:
            raise NotFoundError(f"organization {organization_id} not found")
        return org

    def get_workspace(self, organization_id: UUID, workspace_id: UUID) -> Workspace:
        workspace = self.session.get(Workspace, workspace_id)
        if workspace is None:
            raise NotFoundError(f"workspace {workspace_id} not found")
        if workspace.organization_id != organization_id:
            raise TenantMismatchError("workspace does not belong to organization")
        return workspace

    def get_source(self, organization_id: UUID, source_id: UUID) -> SourceConnection:
        source = self.session.get(SourceConnection, source_id)
        if source is None:
            raise NotFoundError(f"source {source_id} not found")
        if source.organization_id != organization_id:
            raise TenantMismatchError("source does not belong to organization")
        return source

    def list_sources(self, organization_id: UUID) -> list[SourceConnection]:
        stmt: Select[tuple[SourceConnection]] = (
            select(SourceConnection)
            .where(SourceConnection.organization_id == organization_id)
            .order_by(SourceConnection.created_at.desc())
        )
        return list(self.session.scalars(stmt).all())

    def create_source(
        self,
        *,
        organization_id: UUID,
        workspace_id: UUID,
        name: str,
        source_type: str = SourceType.FILE_UPLOAD.value,
        config: dict | None = None,
    ) -> SourceConnection:
        self.get_workspace(organization_id, workspace_id)
        source = SourceConnection(
            organization_id=organization_id,
            workspace_id=workspace_id,
            name=name,
            source_type=source_type,
            status=SourceStatus.CONNECTED.value,
            config=config or {},
            checkpoint={},
        )
        self.session.add(source)
        self.session.flush()
        return source

    def set_source_status(
        self, organization_id: UUID, source_id: UUID, status: SourceStatus
    ) -> SourceConnection:
        source = self.get_source(organization_id, source_id)
        source.status = status.value
        source.updated_at = _utcnow()
        return source

    def delete_source(self, organization_id: UUID, source_id: UUID) -> None:
        source = self.get_source(organization_id, source_id)
        source.status = SourceStatus.DISCONNECTED.value
        source.updated_at = _utcnow()

    def list_documents(
        self,
        organization_id: UUID,
        *,
        source_connection_id: UUID | None = None,
        state: str | None = None,
    ) -> list[Document]:
        stmt = select(Document).where(Document.organization_id == organization_id)
        if source_connection_id is not None:
            stmt = stmt.where(Document.source_connection_id == source_connection_id)
        if state is not None:
            stmt = stmt.where(Document.current_state == state)
        stmt = stmt.order_by(Document.updated_at.desc())
        return list(self.session.scalars(stmt).all())

    def get_document(self, organization_id: UUID, document_id: UUID) -> Document:
        stmt = (
            select(Document)
            .options(selectinload(Document.versions))
            .where(Document.id == document_id)
        )
        document = self.session.scalars(stmt).first()
        if document is None:
            raise NotFoundError(f"document {document_id} not found")
        if document.organization_id != organization_id:
            raise TenantMismatchError("document does not belong to organization")
        return document

    def get_parsed_blocks(
        self,
        organization_id: UUID,
        document_id: UUID,
        version_number: int | None = None,
    ) -> tuple[Document, DocumentVersion, list[DocumentBlock]]:
        document = self.get_document(organization_id, document_id)
        if version_number is None:
            version = self._current_version(document)
        else:
            stmt = select(DocumentVersion).where(
                DocumentVersion.document_id == document.id,
                DocumentVersion.version_number == version_number,
            )
            version = self.session.scalars(stmt).first()
            if version is None:
                raise NotFoundError(f"version {version_number} not found")
        blocks = list(
            self.session.scalars(
                select(DocumentBlock)
                .where(DocumentBlock.version_id == version.id)
                .order_by(DocumentBlock.ordinal)
            ).all()
        )
        return document, version, blocks

    def get_chunks(
        self,
        organization_id: UUID,
        document_id: UUID,
        version_number: int | None = None,
    ) -> tuple[Document, DocumentVersion, list[DocumentChunk]]:
        document = self.get_document(organization_id, document_id)
        if version_number is None:
            version = self._current_version(document)
        else:
            stmt = select(DocumentVersion).where(
                DocumentVersion.document_id == document.id,
                DocumentVersion.version_number == version_number,
            )
            version = self.session.scalars(stmt).first()
            if version is None:
                raise NotFoundError(f"version {version_number} not found")
        chunks = list(
            self.session.scalars(
                select(DocumentChunk)
                .where(DocumentChunk.version_id == version.id)
                .order_by(DocumentChunk.ordinal)
            ).all()
        )
        return document, version, chunks

    def list_duplicates(
        self, organization_id: UUID, document_id: UUID
    ) -> list[DocumentDuplicate]:
        self.get_document(organization_id, document_id)
        stmt = (
            select(DocumentDuplicate)
            .where(
                DocumentDuplicate.organization_id == organization_id,
                or_(
                    DocumentDuplicate.canonical_document_id == document_id,
                    DocumentDuplicate.duplicate_document_id == document_id,
                ),
            )
            .order_by(DocumentDuplicate.created_at.desc())
        )
        return list(self.session.scalars(stmt).all())

    def list_jobs(
        self,
        organization_id: UUID,
        *,
        status: str | None = None,
        document_id: UUID | None = None,
    ) -> list[IngestionJob]:
        stmt = select(IngestionJob).where(IngestionJob.organization_id == organization_id)
        if status is not None:
            stmt = stmt.where(IngestionJob.status == status)
        if document_id is not None:
            stmt = stmt.where(IngestionJob.document_id == document_id)
        stmt = stmt.order_by(IngestionJob.created_at.desc())
        return list(self.session.scalars(stmt).all())

    def list_dead_letter_jobs(self, organization_id: UUID) -> list[IngestionJob]:
        return self.list_jobs(organization_id, status=JobStatus.FAILED.value)

    def replay_dead_letter_job(self, organization_id: UUID, job_id: UUID) -> IngestOutcome:
        job = self.get_job(organization_id, job_id)
        if job.status != JobStatus.FAILED.value:
            raise NotFoundError("job is not in the dead-letter queue")
        return self.retry_job(organization_id, job_id)

    def get_job(self, organization_id: UUID, job_id: UUID) -> IngestionJob:
        job = self.session.get(IngestionJob, job_id)
        if job is None:
            raise NotFoundError(f"job {job_id} not found")
        if job.organization_id != organization_id:
            raise TenantMismatchError("job does not belong to organization")
        return job

    def submit_upload(
        self,
        *,
        organization_id: UUID,
        source_connection_id: UUID,
        filename: str,
        data: bytes,
        declared_mime: str | None = None,
        source_id: str | None = None,
    ) -> IngestOutcome:
        source = self.get_source(organization_id, source_connection_id)
        if source.status == SourceStatus.PAUSED.value:
            raise SourcePausedError("source is paused")
        if source.status == SourceStatus.DISCONNECTED.value:
            raise SourcePausedError("source is disconnected")

        mime = validate_upload(filename=filename, declared_mime=declared_mime, size_bytes=len(data))
        upstream_id = normalize_source_id(source_id or filename)
        digest = sha256_digest(data)
        document_id = stable_document_id(
            organization_id,
            source.source_type,
            source.id,
            upstream_id,
        )
        title = Path(filename).stem or upstream_id
        document = self._get_or_create_document(
            document_id=document_id,
            organization_id=organization_id,
            workspace_id=source.workspace_id,
            source=source,
            source_id=upstream_id,
            title=title,
            mime_type=mime,
            filename=filename,
        )

        if (
            document.content_hash == digest
            and document.current_version > 0
            and document.current_state != DocumentState.DELETED.value
            and document.current_state
            in {
                DocumentState.NORMALIZED.value,
                DocumentState.CHUNKED.value,
                DocumentState.EMBEDDED.value,
                DocumentState.INDEXED.value,
            }
        ):
            job = self._new_job(
                organization_id=organization_id,
                source_connection_id=source.id,
                document_id=document.id,
                job_type=JobType.UPLOAD,
                status=JobStatus.SKIPPED_UNCHANGED,
                stats={
                    "reason": "content_hash_unchanged",
                    "content_hash": digest,
                    "version": document.current_version,
                },
            )
            job.finished_at = _utcnow()
            source.last_sync_at = _utcnow()
            return IngestOutcome(document=document, job=job, unchanged=True, enqueue=False)

        in_flight_key = f"upload:{source.id}:{upstream_id}:{digest}"
        existing = self._active_job(in_flight_key)
        if existing is not None:
            return IngestOutcome(document=document, job=existing, unchanged=False, enqueue=False)

        job = self._new_job(
            organization_id=organization_id,
            source_connection_id=source.id,
            document_id=document.id,
            job_type=JobType.UPLOAD,
            status=JobStatus.QUEUED,
            deterministic_key=in_flight_key,
        )
        staging_key = f"staging/{organization_id}/{job.id}/original"
        self.storage.put_bytes(staging_key, data, content_type=mime)
        job.staging_object_key = staging_key
        source.last_sync_at = _utcnow()
        return IngestOutcome(document=document, job=job, unchanged=False, enqueue=True)

    def submit_connector_content(
        self,
        *,
        organization_id: UUID,
        source_connection_id: UUID,
        content: FetchedContent,
    ) -> IngestOutcome:
        source = self.get_source(organization_id, source_connection_id)
        if source.status == SourceStatus.PAUSED.value:
            raise SourcePausedError("source is paused")
        if source.status == SourceStatus.DISCONNECTED.value:
            raise SourcePausedError("source is disconnected")

        upstream_id = normalize_source_id(content.source_id)
        digest = sha256_digest(content.data)
        document_id = stable_document_id(
            organization_id,
            source.source_type,
            source.id,
            upstream_id,
        )
        filename = str(content.metadata.get("original_filename") or content.title or upstream_id)
        document = self._get_or_create_document(
            document_id=document_id,
            organization_id=organization_id,
            workspace_id=source.workspace_id,
            source=source,
            source_id=upstream_id,
            title=content.title,
            mime_type=content.mime_type,
            filename=filename,
            source_url=content.source_url,
            metadata=content.metadata,
            permissions={
                "organization_id": str(organization_id),
                "workspace_id": str(source.workspace_id),
                "allowed_users": content.permissions.allowed_users,
                "allowed_groups": content.permissions.allowed_groups,
            },
        )

        if (
            document.content_hash == digest
            and document.current_version > 0
            and document.current_state != DocumentState.DELETED.value
        ):
            job = self._new_job(
                organization_id=organization_id,
                source_connection_id=source.id,
                document_id=document.id,
                job_type=JobType.SYNC,
                status=JobStatus.SKIPPED_UNCHANGED,
                stats={"reason": "content_hash_unchanged", "content_hash": digest},
            )
            job.finished_at = _utcnow()
            return IngestOutcome(document=document, job=job, unchanged=True, enqueue=False)

        deterministic_key = f"sync:{source.id}:{upstream_id}:{digest}"
        existing = self._active_job(deterministic_key)
        if existing is not None:
            return IngestOutcome(document=document, job=existing, unchanged=False, enqueue=False)
        job = self._new_job(
            organization_id=organization_id,
            source_connection_id=source.id,
            document_id=document.id,
            job_type=JobType.SYNC,
            status=JobStatus.QUEUED,
            deterministic_key=deterministic_key,
            stats={"connector_source_id": upstream_id},
        )
        staging_key = f"staging/{organization_id}/{job.id}/connector"
        self.storage.put_bytes(staging_key, content.data, content_type=content.mime_type)
        job.staging_object_key = staging_key
        return IngestOutcome(document=document, job=job, unchanged=False, enqueue=True)

    def create_source_sync_job(
        self,
        *,
        organization_id: UUID,
        source_connection_id: UUID,
    ) -> IngestionJob:
        source = self.get_source(organization_id, source_connection_id)
        if source.source_type == SourceType.FILE_UPLOAD.value:
            raise SourcePausedError("file_upload sources do not support connector sync")
        active = self._active_job(f"source-sync:{source.id}")
        if active is not None:
            return active
        return self._new_job(
            organization_id=organization_id,
            source_connection_id=source.id,
            document_id=None,
            job_type=JobType.SYNC,
            status=JobStatus.QUEUED,
            deterministic_key=f"source-sync:{source.id}",
        )

    def process_job(self, job_id: UUID) -> IngestOutcome:
        job = self.session.get(IngestionJob, job_id)
        if job is None:
            raise NotFoundError(f"job {job_id} not found")
        if job.status in {JobStatus.SUCCEEDED.value, JobStatus.SKIPPED_UNCHANGED.value}:
            document = self.session.get(Document, job.document_id) if job.document_id else None
            if document is None:
                raise NotFoundError("job document missing")
            return IngestOutcome(
                document=document,
                job=job,
                unchanged=job.status == JobStatus.SKIPPED_UNCHANGED.value,
                enqueue=False,
            )

        job.status = JobStatus.RUNNING.value
        job.attempt += 1
        job.started_at = job.started_at or _utcnow()
        self.session.flush()

        if job.document_id is None:
            raise NotFoundError("job has no document")
        document = self.session.get(Document, job.document_id)
        if document is None:
            raise NotFoundError("job document missing")

        try:
            data = self._load_job_bytes(job, document)
            digest = sha256_digest(data)
            hash_unchanged = (
                document.content_hash == digest
                and document.current_version > 0
                and document.current_state != DocumentState.DELETED.value
            )
            if hash_unchanged and not self._needs_pipeline(document, job):
                self._mark_job(
                    job,
                    JobStatus.SKIPPED_UNCHANGED,
                    {"reason": "content_hash_unchanged", "content_hash": digest},
                )
                self._drop_staging(job)
                return IngestOutcome(document=document, job=job, unchanged=True, enqueue=False)

            retrieved_at = None
            if hash_unchanged:
                version = self._current_version(document)
                parse_stats: dict = {}
                if self._needs_parse(document, job):
                    parse_stats = self._parse_version(document, version, data)
                    parse_stats = {"reparsed": True, **parse_stats}
            else:
                self._enter_fetching(document)
                version_number = document.current_version + 1
                filename = _original_filename(document.source_id, document.extra_metadata)
                key = raw_object_key(
                    source=document.source_type,
                    document_id=str(document.id),
                    version=version_number,
                    filename=filename,
                )
                stored = self.storage.put_bytes(
                    key,
                    data,
                    content_type=document.mime_type or "application/octet-stream",
                )
                retrieved_at = _utcnow()
                self._retire_current_versions(document.id)
                version = DocumentVersion(
                    document_id=document.id,
                    version_number=version_number,
                    content_hash=digest,
                    raw_object_key=stored.key,
                    mime_type=document.mime_type,
                    size_bytes=len(data),
                    original_filename=filename,
                    is_current=True,
                    retrieved_at=retrieved_at,
                    extra_metadata={"source_id": document.source_id},
                )
                self.session.add(version)
                self.session.flush()
                document.current_version = version_number
                document.content_hash = digest
                document.raw_object_key = stored.key
                document.last_error = None
                document.retry_count = 0
                document.deleted_at = None
                self._set_state(document, DocumentState.FETCHED)
                parse_stats = self._parse_version(document, version, data)
                parse_stats = {
                    "bytes": len(data),
                    "raw_object_key": stored.key,
                    **parse_stats,
                }

            norm_stats = self._normalize_version(document, version)
            chunk_stats = self._chunk_version(document, version)
            self._mark_job(
                job,
                JobStatus.SUCCEEDED,
                {
                    "version": document.current_version,
                    "content_hash": digest,
                    **parse_stats,
                    **norm_stats,
                    **chunk_stats,
                },
            )
            self._drop_staging(job)
            if retrieved_at is not None:
                source = self.session.get(SourceConnection, document.source_connection_id)
                if source is not None:
                    source.last_sync_at = retrieved_at
            return IngestOutcome(
                document=document, job=job, unchanged=False, enqueue=False
            )
        except PermanentParseError as exc:
            document.last_error = str(exc)
            document.retry_count += 1
            try:
                self._set_state(document, DocumentState.FAILED)
            except Exception:
                document.current_state = DocumentState.FAILED.value
            self._mark_job(
                job,
                JobStatus.FAILED,
                {"error": str(exc), "failure_kind": FailureKind.PERMANENT.value},
            )
            job.last_error = str(exc)
            raise
        except Exception as exc:
            document.last_error = str(exc)
            document.retry_count += 1
            try:
                self._set_state(document, DocumentState.FAILED)
            except Exception:
                document.current_state = DocumentState.FAILED.value
            self._mark_job(
                job,
                JobStatus.FAILED,
                {"error": str(exc), "failure_kind": FailureKind.TEMPORARY.value},
            )
            job.last_error = str(exc)
            raise

    def reprocess(self, organization_id: UUID, document_id: UUID) -> IngestOutcome:
        document = self.get_document(organization_id, document_id)
        if document.raw_object_key is None:
            raise NotFoundError("document has no raw object to replay")
        job = self._new_job(
            organization_id=organization_id,
            source_connection_id=document.source_connection_id,
            document_id=document.id,
            job_type=JobType.REPROCESS,
            status=JobStatus.QUEUED,
        )
        return IngestOutcome(document=document, job=job, unchanged=False, enqueue=True)

    def delete_document(self, organization_id: UUID, document_id: UUID) -> Document:
        document = self.get_document(organization_id, document_id)
        if document.current_state != DocumentState.DELETED.value:
            self._set_state(document, DocumentState.DELETED)
            document.deleted_at = _utcnow()
            source = self.session.get(SourceConnection, document.source_connection_id)
            if source is not None and source.document_count > 0:
                source.document_count -= 1
            self._new_job(
                organization_id=organization_id,
                source_connection_id=document.source_connection_id,
                document_id=document.id,
                job_type=JobType.DELETE,
                status=JobStatus.SUCCEEDED,
                stats={"raw_object_key": document.raw_object_key},
            )
        return document

    def retry_job(self, organization_id: UUID, job_id: UUID) -> IngestOutcome:
        job = self.get_job(organization_id, job_id)
        if job.status not in {JobStatus.FAILED.value, JobStatus.QUEUED.value}:
            document = (
                self.get_document(organization_id, job.document_id) if job.document_id else None
            )
            if document is None:
                raise NotFoundError("job document missing")
            return IngestOutcome(document=document, job=job, unchanged=False, enqueue=False)
        job.status = JobStatus.QUEUED.value
        job.last_error = None
        job.finished_at = None
        document = self.get_document(organization_id, job.document_id) if job.document_id else None
        if document is None:
            raise NotFoundError("job document missing")
        return IngestOutcome(document=document, job=job, unchanged=False, enqueue=True)

    def _get_or_create_document(
        self,
        *,
        document_id: UUID,
        organization_id: UUID,
        workspace_id: UUID,
        source: SourceConnection,
        source_id: str,
        title: str,
        mime_type: str,
        filename: str,
        source_url: str | None = None,
        metadata: dict | None = None,
        permissions: dict | None = None,
    ) -> Document:
        document = self.session.get(Document, document_id)
        now = _utcnow()
        document_permissions = permissions or {
            "organization_id": str(organization_id),
            "workspace_id": str(workspace_id),
            "allowed_users": source.config.get("allowed_users", []),
            "allowed_groups": source.config.get("allowed_groups", []),
        }
        extra_metadata = {
            "original_filename": filename,
            "source": source.source_type,
            **(metadata or {}),
        }
        if document is None:
            document = Document(
                id=document_id,
                organization_id=organization_id,
                workspace_id=workspace_id,
                source_connection_id=source.id,
                source_type=source.source_type,
                source_id=source_id,
                title=title,
                mime_type=mime_type,
                source_url=source_url,
                current_version=0,
                current_state=DocumentState.DISCOVERED.value,
                extra_metadata=extra_metadata,
                permissions=document_permissions,
            )
            self.session.add(document)
            source.document_count += 1
            self.session.flush()
            return document
        if document.organization_id != organization_id:
            raise TenantMismatchError("stable document id collided across tenants")
        document.title = title
        document.mime_type = mime_type
        document.source_url = source_url
        document.extra_metadata = {**document.extra_metadata, **extra_metadata}
        document.permissions = document_permissions
        document.updated_at = now
        if document.current_state == DocumentState.DELETED.value:
            document.deleted_at = None
            document.current_state = DocumentState.DISCOVERED.value
            document.last_successful_state = None
            source.document_count += 1
        return document

    def _new_job(
        self,
        *,
        organization_id: UUID,
        source_connection_id: UUID | None,
        document_id: UUID | None,
        job_type: JobType,
        status: JobStatus,
        deterministic_key: str | None = None,
        stats: dict | None = None,
    ) -> IngestionJob:
        job = IngestionJob(
            id=uuid4(),
            organization_id=organization_id,
            source_connection_id=source_connection_id,
            document_id=document_id,
            job_type=job_type.value,
            status=status.value,
            deterministic_key=deterministic_key,
            stats=stats or {},
        )
        self.session.add(job)
        self.session.flush()
        return job

    def _active_job(self, deterministic_key: str) -> IngestionJob | None:
        stmt = select(IngestionJob).where(
            IngestionJob.deterministic_key == deterministic_key,
            IngestionJob.status.in_((JobStatus.QUEUED.value, JobStatus.RUNNING.value)),
        )
        return self.session.scalars(stmt).first()

    def _load_job_bytes(self, job: IngestionJob, document: Document) -> bytes:
        if job.staging_object_key:
            return self.storage.get_bytes(job.staging_object_key)
        if document.raw_object_key:
            return self.storage.get_bytes(document.raw_object_key)
        raise NotFoundError("job has no staged or raw bytes to process")

    def _enter_fetching(self, document: Document) -> None:
        current = DocumentState(document.current_state)
        if current == DocumentState.FETCHING:
            return
        if current == DocumentState.DISCOVERED:
            self._set_state(document, DocumentState.FETCHING)
            return
        if current in {
            DocumentState.FETCHED,
            DocumentState.INDEXED,
            DocumentState.FAILED,
            DocumentState.PARSED,
            DocumentState.NORMALIZED,
            DocumentState.CHUNKED,
            DocumentState.EMBEDDED,
        }:
            self._set_state(document, DocumentState.FETCHING)
            return
        self._set_state(document, DocumentState.FETCHING)

    def _set_state(self, document: Document, target: DocumentState) -> None:
        new_state = transition(document.current_state, target)
        document.current_state = new_state.value
        if new_state in SUCCESS_STATES:
            document.last_successful_state = new_state.value
        document.updated_at = _utcnow()

    def _retire_current_versions(self, document_id: UUID) -> None:
        versions = self.session.scalars(
            select(DocumentVersion).where(
                DocumentVersion.document_id == document_id,
                DocumentVersion.is_current.is_(True),
            )
        ).all()
        for version in versions:
            version.is_current = False

    def _mark_job(self, job: IngestionJob, status: JobStatus, stats: dict) -> None:
        job.status = status.value
        job.finished_at = _utcnow()
        job.stats = {**job.stats, **stats}
        # Free the idempotency key so a later job for the same hash can enqueue.
        job.deterministic_key = None

    def _drop_staging(self, job: IngestionJob) -> None:
        job.staging_object_key = None

    def _needs_pipeline(self, document: Document, job: IngestionJob) -> bool:
        if job.job_type == JobType.REPROCESS.value:
            return True
        return document.current_state in {
            DocumentState.FETCHED.value,
            DocumentState.PARSING.value,
            DocumentState.PARSED.value,
            DocumentState.NORMALIZING.value,
            DocumentState.NORMALIZED.value,
            DocumentState.CHUNKING.value,
            DocumentState.FAILED.value,
        }

    def _needs_parse(self, document: Document, job: IngestionJob) -> bool:
        if job.job_type == JobType.REPROCESS.value:
            return True
        if document.current_state in {
            DocumentState.FETCHED.value,
            DocumentState.PARSING.value,
        }:
            return True
        if document.current_state == DocumentState.FAILED.value:
            last = document.last_successful_state
            return last not in {
                DocumentState.PARSED.value,
                DocumentState.NORMALIZED.value,
                DocumentState.CHUNKED.value,
                DocumentState.EMBEDDED.value,
                DocumentState.INDEXED.value,
            }
        return False

    def _current_version(self, document: Document) -> DocumentVersion:
        stmt = select(DocumentVersion).where(
            DocumentVersion.document_id == document.id,
            DocumentVersion.is_current.is_(True),
        )
        version = self.session.scalars(stmt).first()
        if version is None:
            raise NotFoundError("document has no current version to parse")
        return version

    def _enter_parsing(self, document: Document) -> None:
        if document.current_state == DocumentState.PARSING.value:
            return
        self._set_state(document, DocumentState.PARSING)

    def _enter_normalizing(self, document: Document) -> None:
        if document.current_state == DocumentState.NORMALIZING.value:
            return
        self._set_state(document, DocumentState.NORMALIZING)

    def _parse_version(
        self, document: Document, version: DocumentVersion, data: bytes
    ) -> dict:
        self._enter_parsing(document)
        mime = version.mime_type or document.mime_type or "application/octet-stream"
        raw = RawDocument(
            data=data,
            mime_type=mime,
            filename=version.original_filename,
            title=document.title,
        )
        try:
            parsed = get_parser_registry().parse(raw)
        except UnsupportedMimeError as exc:
            raise PermanentParseError(str(exc)) from exc
        self._replace_blocks(document, version, parsed)
        if parsed.title:
            document.title = parsed.title[:512]
        document.last_error = None
        self._set_state(document, DocumentState.PARSED)
        return {
            "parser_name": parsed.parser_name,
            "parser_version": parsed.parser_version,
            "block_count": len(parsed.blocks),
            "used_ocr": parsed.used_ocr,
            "warnings": parsed.warnings,
        }

    def _replace_blocks(self, document: Document, version: DocumentVersion, parsed) -> None:  # noqa: ANN001
        self.session.execute(
            delete(DocumentBlock).where(DocumentBlock.version_id == version.id)
        )
        for block in parsed.blocks:
            self.session.add(
                DocumentBlock(
                    document_id=document.id,
                    version_id=version.id,
                    ordinal=block.ordinal,
                    block_type=block.type.value,
                    text=block.text,
                    heading_level=block.level,
                    page=block.page,
                    section=block.section,
                    extra=block.metadata,
                )
            )
        version.parser_name = parsed.parser_name
        version.parser_version = parsed.parser_version
        version.used_ocr = parsed.used_ocr
        version.parsed_block_count = len(parsed.blocks)
        version.parse_warnings = parsed.warnings
        version.parsed_at = _utcnow()

    def _normalize_version(self, document: Document, version: DocumentVersion) -> dict:
        self._enter_normalizing(document)
        rows = list(
            self.session.scalars(
                select(DocumentBlock)
                .where(DocumentBlock.version_id == version.id)
                .order_by(DocumentBlock.ordinal)
            ).all()
        )
        snapshots = [
            BlockSnapshot(
                ordinal=row.ordinal,
                block_type=row.block_type,
                text=row.text,
                page=row.page,
                heading_level=row.heading_level,
                section=row.section,
                extra=dict(row.extra or {}),
            )
            for row in rows
        ]
        result = normalize_blocks(snapshots)
        by_ordinal = {item.ordinal: item for item in result.blocks}
        for row in rows:
            snapshot = by_ordinal[row.ordinal]
            row.normalized_text = snapshot.normalized_text
            extra = dict(row.extra or {})
            if snapshot.dropped:
                extra["dropped"] = True
                extra["drop_reason"] = snapshot.drop_reason
            else:
                extra.pop("dropped", None)
                extra.pop("drop_reason", None)
            row.extra = extra
        version.language = result.language
        version.normalized_content_hash = result.content_hash
        version.simhash = as_int64(result.simhash)
        version.normalizer_name = result.normalizer_name
        version.normalizer_version = result.normalizer_version
        version.normalized_at = _utcnow()
        document.language = result.language
        document.last_error = None
        dup_stats = record_duplicates(
            self.session,
            organization_id=document.organization_id,
            document=document,
            version=version,
        )
        self._set_state(document, DocumentState.NORMALIZED)
        return {
            "language": result.language,
            "normalized_content_hash": result.content_hash,
            "simhash": result.simhash,
            "normalized_kept": result.kept,
            "normalized_dropped": result.dropped,
            "normalizer_version": result.normalizer_version,
            "duplicates": dup_stats,
        }

    def _enter_chunking(self, document: Document) -> None:
        if document.current_state == DocumentState.CHUNKING.value:
            return
        self._set_state(document, DocumentState.CHUNKING)

    def _chunk_version(self, document: Document, version: DocumentVersion) -> dict:
        self._enter_chunking(document)
        settings = get_settings()
        rows = list(
            self.session.scalars(
                select(DocumentBlock)
                .where(DocumentBlock.version_id == version.id)
                .order_by(DocumentBlock.ordinal)
            ).all()
        )
        inputs = [
            BlockInput(
                ordinal=row.ordinal,
                block_type=row.block_type,
                text=(row.normalized_text if row.normalized_text is not None else row.text),
                page=row.page,
                heading_level=row.heading_level,
                section=row.section,
                dropped=bool((row.extra or {}).get("dropped")),
            )
            for row in rows
        ]
        result = run_chunker(
            inputs,
            strategy=settings.chunk_strategy,
            chunk_size=settings.chunk_size,
            overlap=settings.chunk_overlap,
            parent_max_tokens=settings.parent_chunk_max_tokens,
        )
        self.session.execute(
            delete(DocumentChunk).where(DocumentChunk.version_id == version.id)
        )
        self.session.flush()
        created: list[DocumentChunk] = []
        for ordinal, draft in enumerate(result.chunks):
            created.append(
                DocumentChunk(
                    document_id=document.id,
                    version_id=version.id,
                    parent_chunk_id=None,
                    ordinal=ordinal,
                    text=draft.text,
                    token_count=draft.token_count,
                    page=draft.page,
                    section=draft.section,
                    strategy=result.strategy.value,
                    kind=draft.kind.value,
                    extra=dict(draft.metadata),
                )
            )
            self.session.add(created[-1])
        self.session.flush()
        for ordinal, draft in enumerate(result.chunks):
            if draft.parent_index is None:
                continue
            created[ordinal].parent_chunk_id = created[draft.parent_index].id
        version.chunk_strategy = result.strategy.value
        version.chunker_version = result.chunker_version
        version.chunk_count = len(created)
        version.chunked_at = _utcnow()
        document.last_error = None
        self._set_state(document, DocumentState.CHUNKED)
        return {
            "chunk_strategy": result.strategy.value,
            "chunker_version": result.chunker_version,
            "chunk_count": len(created),
            "parent_chunks": sum(1 for item in created if item.kind == "parent"),
            "child_chunks": sum(1 for item in created if item.kind == "child"),
        }
