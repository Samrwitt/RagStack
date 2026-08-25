from uuid import uuid4

from app.retrieval.acl import can_read_document
from app.retrieval.bm25 import tokenize
from app.retrieval.models import ACLContext, RetrievalFilters, RetrievalHit
from app.retrieval.qdrant_filters import qdrant_filter
from app.retrieval.rrf import reciprocal_rank_fusion


def test_tokenize_keeps_identifiers_and_numbers() -> None:
    assert tokenize("Error CODE_42 grants 22 days.") == [
        "error",
        "code_42",
        "grants",
        "22",
        "days",
    ]


def test_acl_allows_public_user_group_and_denies_mismatch() -> None:
    assert can_read_document({"allowed_users": [], "allowed_groups": []}, ACLContext())
    assert can_read_document(
        {"allowed_users": ["u1"], "allowed_groups": []},
        ACLContext(user_id="u1"),
    )
    assert can_read_document(
        {"allowed_users": ["person@example.com"], "allowed_groups": []},
        ACLContext(user_email="person@example.com"),
    )
    assert can_read_document(
        {"allowed_users": [], "allowed_groups": ["engineering"]},
        ACLContext(group_ids=frozenset({"engineering"})),
    )
    assert not can_read_document(
        {"allowed_users": ["u2"], "allowed_groups": ["finance"]},
        ACLContext(user_id="u1", group_ids=frozenset({"engineering"})),
    )


def test_rrf_merges_duplicate_chunks_and_preserves_component_scores() -> None:
    chunk_id = uuid4()
    hit = RetrievalHit(
        chunk_id=chunk_id,
        document_id=uuid4(),
        version_id=uuid4(),
        score=3.0,
        rank=1,
        text="annual leave policy",
        title="Policy",
        source_type="file_upload",
        source_url=None,
        page=None,
        section=None,
        metadata={},
        scores={"bm25": 3.0},
    )

    fused = reciprocal_rank_fusion([[hit], [hit]], top_k=1)

    assert len(fused) == 1
    assert fused[0].chunk_id == chunk_id
    assert fused[0].scores["bm25"] == 3.0
    assert fused[0].scores["rrf"] > 0


def test_qdrant_filter_contains_metadata_and_acl_conditions() -> None:
    org_id = uuid4()
    workspace_id = uuid4()

    compiled = qdrant_filter(
        RetrievalFilters(
            organization_id=org_id,
            workspace_id=workspace_id,
            source_type="file_upload",
            language="en",
        ),
        ACLContext(user_id="u1", group_ids=frozenset({"engineering"})),
    )

    must_keys = {condition.key for condition in compiled.must}
    assert {"organization_id", "workspace_id", "source_type", "language", "is_current"}.issubset(
        must_keys
    )
    assert compiled.should is None
