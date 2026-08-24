"""Ingestion control plane.

Owns source connections, canonical documents, versioning, hashing, jobs,
and the FETCHED-or-skip decision. Parsing and later stages are Phase 3+.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import Select, select
from sqlalchemy.orm import Session, selectinload

from app.core.storage import ObjectStorage, get_object_storage, raw_object_key
from app.ingestion.errors import NotFoundError, SourcePausedError, TenantMismatchError
from app.ingestion.hashing import sha256_digest
from app.ingestion.identity import normalize_source_id, stable_document_id
from app.ingestion.mime import validate_upload
from app.ingestion.state_machine import SUCCESS_STATES, transition
from app.models.document import Document, DocumentVersion
from app.models.enums import DocumentState, JobStatus, JobType, SourceStatus, SourceType
from app.models.job import IngestionJob
from app.models.organization import Organization, Workspace
from app.models.source import SourceConnection


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
            if (
                document.content_hash == digest
                and document.current_version > 0
                and document.current_state != DocumentState.DELETED.value
            ):
                self._mark_job(
                    job,
                    JobStatus.SKIPPED_UNCHANGED,
                    {"reason": "content_hash_unchanged", "content_hash": digest},
                )
                self._drop_staging(job)
                return IngestOutcome(document=document, job=job, unchanged=True, enqueue=False)

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
            document.current_version = version_number
            document.content_hash = digest
            document.raw_object_key = stored.key
            document.mime_type = document.mime_type
            document.last_error = None
            document.retry_count = 0
            document.deleted_at = None
            self._set_state(document, DocumentState.FETCHED)
            self._mark_job(
                job,
                JobStatus.SUCCEEDED,
                {
                    "version": version_number,
                    "content_hash": digest,
                    "bytes": len(data),
                    "raw_object_key": stored.key,
                },
            )
            self._drop_staging(job)
            source = self.session.get(SourceConnection, document.source_connection_id)
            if source is not None:
                source.last_sync_at = retrieved_at
            return IngestOutcome(document=document, job=job, unchanged=False, enqueue=False)
        except Exception as exc:
            document.last_error = str(exc)
            document.retry_count += 1
            try:
                self._set_state(document, DocumentState.FAILED)
            except Exception:
                document.current_state = DocumentState.FAILED.value
            self._mark_job(job, JobStatus.FAILED, {"error": str(exc)})
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
    ) -> Document:
        document = self.session.get(Document, document_id)
        now = _utcnow()
        permissions = {
            "organization_id": str(organization_id),
            "workspace_id": str(workspace_id),
            "allowed_users": source.config.get("allowed_users", []),
            "allowed_groups": source.config.get("allowed_groups", []),
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
                current_version=0,
                current_state=DocumentState.DISCOVERED.value,
                extra_metadata={"original_filename": filename, "source": source.source_type},
                permissions=permissions,
            )
            self.session.add(document)
            source.document_count += 1
            self.session.flush()
            return document
        if document.organization_id != organization_id:
            raise TenantMismatchError("stable document id collided across tenants")
        document.title = title
        document.mime_type = mime_type
        document.extra_metadata = {**document.extra_metadata, "original_filename": filename}
        document.permissions = permissions
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
        if job.job_type == JobType.REPROCESS.value and document.raw_object_key:
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
