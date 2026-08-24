"""Qdrant payload filter compilation for dense retrieval."""

from __future__ import annotations

from typing import Any

from app.indexing.qdrant import qmodels
from app.retrieval.models import ACLContext, RetrievalFilters


def qdrant_filter(filters: RetrievalFilters, acl: ACLContext) -> Any:
    must = [
        _match_value("organization_id", str(filters.organization_id)),
        _match_value("is_current", True),
    ]
    if filters.workspace_id is not None:
        must.append(_match_value("workspace_id", str(filters.workspace_id)))
    if filters.source_connection_id is not None:
        must.append(_match_value("source_connection_id", str(filters.source_connection_id)))
    if filters.source_type is not None:
        must.append(_match_value("source_type", filters.source_type))
    if filters.document_ids:
        must.append(_match_any("document_id", [str(item) for item in filters.document_ids]))
    if filters.language is not None:
        must.append(_match_value("language", filters.language))

    should = []
    if acl.user_id is not None:
        should.append(_match_any("allowed_users", [acl.user_id]))
    if acl.group_ids:
        should.append(_match_any("allowed_groups", sorted(acl.group_ids)))
    return qmodels.Filter(must=must, should=should or None)


def _match_value(key: str, value: object) -> Any:
    return qmodels.FieldCondition(key=key, match=qmodels.MatchValue(value=value))


def _match_any(key: str, values: list[object]) -> Any:
    return qmodels.FieldCondition(key=key, match=qmodels.MatchAny(any=values))
