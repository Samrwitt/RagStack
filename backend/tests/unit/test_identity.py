from uuid import uuid4

from app.ingestion.identity import normalize_source_id, stable_document_id
from app.models.enums import SourceType


def test_stable_id_is_deterministic() -> None:
    org = uuid4()
    conn = uuid4()
    first = stable_document_id(org, SourceType.FILE_UPLOAD.value, conn, "handbook.pdf")
    second = stable_document_id(org, "FILE_UPLOAD", conn, "handbook.pdf")
    assert first == second


def test_stable_id_changes_with_source_id() -> None:
    org = uuid4()
    conn = uuid4()
    left = stable_document_id(org, "file_upload", conn, "a.txt")
    right = stable_document_id(org, "file_upload", conn, "b.txt")
    assert left != right


def test_stable_id_is_tenant_scoped() -> None:
    conn = uuid4()
    left = stable_document_id(uuid4(), "file_upload", conn, "a.txt")
    right = stable_document_id(uuid4(), "file_upload", conn, "a.txt")
    assert left != right


def test_normalize_source_id_strips_slashes() -> None:
    assert normalize_source_id(" /policies/handbook.pdf ") == "policies/handbook.pdf"
