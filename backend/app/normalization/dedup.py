"""Record exact and near-duplicate relationships. Never silent-delete."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.document import Document, DocumentVersion
from app.models.duplicate import DocumentDuplicate
from app.models.enums import DuplicateKind
from app.normalization.simhash import as_int64, as_uint64, hamming_distance, similarity_score


def record_duplicates(
    session: Session,
    *,
    organization_id: UUID,
    document: Document,
    version: DocumentVersion,
) -> dict[str, int]:
    session.execute(
        delete(DocumentDuplicate).where(
            or_(
                DocumentDuplicate.canonical_version_id == version.id,
                DocumentDuplicate.duplicate_version_id == version.id,
            )
        )
    )
    document.canonical_document_id = None
    version.duplicate_kind = None

    if not version.normalized_content_hash:
        return {"exact": 0, "near": 0}

    exact = _record_exact(session, organization_id, document, version)
    near = 0 if exact else _record_near(session, organization_id, document, version)
    return {"exact": exact, "near": near}


def _current_versions(
    session: Session,
    organization_id: UUID,
    exclude_document_id: UUID,
) -> list[tuple[Document, DocumentVersion]]:
    stmt = (
        select(Document, DocumentVersion)
        .join(DocumentVersion, DocumentVersion.document_id == Document.id)
        .where(
            Document.organization_id == organization_id,
            Document.id != exclude_document_id,
            DocumentVersion.is_current.is_(True),
            Document.current_state != "DELETED",
        )
    )
    return list(session.execute(stmt).all())


def _ordered_pair(
    left_doc: Document,
    left_ver: DocumentVersion,
    right_doc: Document,
    right_ver: DocumentVersion,
) -> tuple[Document, DocumentVersion, Document, DocumentVersion]:
    if (left_doc.created_at, str(left_doc.id)) <= (right_doc.created_at, str(right_doc.id)):
        return left_doc, left_ver, right_doc, right_ver
    return right_doc, right_ver, left_doc, left_ver


def _add(
    session: Session,
    *,
    organization_id: UUID,
    canonical_doc: Document,
    canonical_ver: DocumentVersion,
    duplicate_doc: Document,
    duplicate_ver: DocumentVersion,
    kind: DuplicateKind,
    score: float,
) -> None:
    session.add(
        DocumentDuplicate(
            organization_id=organization_id,
            canonical_document_id=canonical_doc.id,
            duplicate_document_id=duplicate_doc.id,
            canonical_version_id=canonical_ver.id,
            duplicate_version_id=duplicate_ver.id,
            kind=kind.value,
            score=score,
        )
    )


def _record_exact(
    session: Session,
    organization_id: UUID,
    document: Document,
    version: DocumentVersion,
) -> int:
    matches = 0
    for other_doc, other_ver in _current_versions(session, organization_id, document.id):
        if other_ver.normalized_content_hash != version.normalized_content_hash:
            continue
        canonical_doc, canonical_ver, dup_doc, dup_ver = _ordered_pair(
            document, version, other_doc, other_ver
        )
        _add(
            session,
            organization_id=organization_id,
            canonical_doc=canonical_doc,
            canonical_ver=canonical_ver,
            duplicate_doc=dup_doc,
            duplicate_ver=dup_ver,
            kind=DuplicateKind.EXACT,
            score=1.0,
        )
        dup_doc.canonical_document_id = canonical_doc.id
        dup_ver.duplicate_kind = DuplicateKind.EXACT.value
        if canonical_doc.id == document.id:
            version.duplicate_kind = None
            document.canonical_document_id = None
        else:
            document.canonical_document_id = canonical_doc.id
            version.duplicate_kind = DuplicateKind.EXACT.value
        matches += 1
    return matches


def _record_near(
    session: Session,
    organization_id: UUID,
    document: Document,
    version: DocumentVersion,
) -> int:
    settings = get_settings()
    threshold = settings.near_duplicate_max_hamming
    limit = settings.near_duplicate_scan_limit
    fingerprint = as_uint64(version.simhash or 0)
    if fingerprint == 0:
        return 0
    matches = 0
    scanned = 0
    for other_doc, other_ver in _current_versions(session, organization_id, document.id):
        if scanned >= limit:
            break
        other_hash = as_uint64(other_ver.simhash or 0)
        if other_hash == 0:
            continue
        scanned += 1
        distance = hamming_distance(fingerprint, other_hash)
        if distance > threshold:
            continue
        canonical_doc, canonical_ver, dup_doc, dup_ver = _ordered_pair(
            document, version, other_doc, other_ver
        )
        _add(
            session,
            organization_id=organization_id,
            canonical_doc=canonical_doc,
            canonical_ver=canonical_ver,
            duplicate_doc=dup_doc,
            duplicate_ver=dup_ver,
            kind=DuplicateKind.NEAR,
            score=round(similarity_score(fingerprint, other_hash), 4),
        )
        if dup_ver.duplicate_kind is None:
            dup_ver.duplicate_kind = DuplicateKind.NEAR.value
        if version.id == dup_ver.id and version.duplicate_kind is None:
            version.duplicate_kind = DuplicateKind.NEAR.value
        matches += 1
    return matches
