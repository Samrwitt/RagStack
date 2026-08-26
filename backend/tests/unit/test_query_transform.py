"""Unit tests for query expansion and HyDE generation."""

from app.retrieval.models import ACLContext, RetrievalFilters, RetrievalMode, RetrievalRequest
from app.retrieval.query_transform import QueryTransformer


def test_query_transformer_expansion() -> None:
    transformer = QueryTransformer()
    variations = transformer.expand_query("how to reset password and configure auth permissions")

    assert len(variations) > 1
    assert variations[0] == "how to reset password and configure auth permissions"
    assert any("reset password" in v or "guide" in v for v in variations)


def test_query_transformer_hyde() -> None:
    transformer = QueryTransformer()
    doc = transformer.generate_hyde_doc("employee annual leave policy")

    assert "Overview and policy regarding employee annual leave policy" in doc
    assert "Section 1:" in doc
