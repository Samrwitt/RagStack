from uuid import uuid4

from app.reranking.context import select_context
from app.reranking.providers import LexicalOverlapReranker
from app.reranking.service import RerankingService
from app.retrieval.models import RetrievalHit


def _hit(text: str, *, rank: int, score: float, metadata: dict | None = None) -> RetrievalHit:
    return RetrievalHit(
        chunk_id=uuid4(),
        document_id=uuid4(),
        version_id=uuid4(),
        score=score,
        rank=rank,
        text=text,
        title="Doc",
        source_type="file_upload",
        source_url=None,
        page=None,
        section=None,
        metadata=metadata or {},
        scores={"bm25": score},
    )


def test_lexical_overlap_reranker_scores_query_matches() -> None:
    provider = LexicalOverlapReranker()
    service = RerankingService(provider=provider)
    weak = _hit("expense policy", rank=1, score=10.0)
    strong = _hit("annual leave days policy", rank=2, score=1.0)

    reranked = service.rerank(
        query="annual leave days",
        candidates=[weak, strong],
        top_k=2,
    )

    assert reranked[0].chunk_id == strong.chunk_id
    assert reranked[0].scores["reranker"] == 1.0
    assert reranked[0].scores["bm25"] == 1.0


def test_context_selection_respects_budget_and_parent_deduplication() -> None:
    parent_id = str(uuid4())
    first = _hit(
        "one two",
        rank=1,
        score=1.0,
        metadata={"parent_chunk_id": parent_id, "token_count": 2},
    )
    sibling = _hit(
        "three four",
        rank=2,
        score=0.9,
        metadata={"parent_chunk_id": parent_id, "token_count": 2},
    )
    other = _hit("five six seven", rank=3, score=0.8, metadata={"token_count": 3})

    selected = select_context([first, sibling, other], token_budget=5)

    assert [item.hit.chunk_id for item in selected] == [first.chunk_id, other.chunk_id]
    assert sum(item.token_count for item in selected) == 5
