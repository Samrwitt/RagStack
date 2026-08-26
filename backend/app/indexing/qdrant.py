"""Qdrant collection and upsert helpers for chunk vectors."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

try:
    from qdrant_client import models as qmodels
    from qdrant_client.http.exceptions import UnexpectedResponse
except ModuleNotFoundError:  # pragma: no cover - lets unit tests use fake clients
    class UnexpectedResponse(Exception):
        pass

    class _Distance:
        COSINE = "Cosine"

    class _PayloadSchemaType:
        KEYWORD = "keyword"

    @dataclass(frozen=True, slots=True)
    class _MatchValue:
        value: object

    @dataclass(frozen=True, slots=True)
    class _MatchAny:
        any: list[object]

    @dataclass(frozen=True, slots=True)
    class _FieldCondition:
        key: str
        match: object

    @dataclass(frozen=True, slots=True)
    class _Filter:
        must: list[object] | None = None
        should: list[object] | None = None

    @dataclass(frozen=True, slots=True)
    class _VectorParams:
        size: int
        distance: str

    @dataclass(frozen=True, slots=True)
    class _PointStruct:
        id: str
        vector: list[float]
        payload: dict

    @dataclass(frozen=True, slots=True)
    class _PointIdsList:
        points: list[str]

    @dataclass(frozen=True, slots=True)
    class _FilterSelector:
        filter: object

    class qmodels:  # type: ignore[no-redef]
        Distance = _Distance
        FieldCondition = _FieldCondition
        Filter = _Filter
        FilterSelector = _FilterSelector
        MatchAny = _MatchAny
        MatchValue = _MatchValue
        PayloadSchemaType = _PayloadSchemaType
        VectorParams = _VectorParams
        PointStruct = _PointStruct
        PointIdsList = _PointIdsList

from app.core.config import Settings, get_settings
from app.core.qdrant import get_qdrant_client


class VectorDimensionMismatch(ValueError):
    """Raised when configured embedding dimensions disagree with Qdrant."""


@dataclass(frozen=True, slots=True)
class VectorPoint:
    id: str
    vector: list[float]
    payload: dict


@dataclass(frozen=True, slots=True)
class VectorSearchResult:
    id: str
    score: float
    payload: dict


class QdrantIndexer:
    def __init__(self, client=None, settings: Settings | None = None) -> None:  # noqa: ANN001
        self.settings = settings or get_settings()
        self.client = client or get_qdrant_client(self.settings)
        self.collection_name = self.settings.qdrant_collection

    def ensure_collection(self, *, vector_size: int) -> None:
        if self._collection_exists():
            current_size = self._collection_vector_size()
            if current_size is not None and current_size != vector_size:
                raise VectorDimensionMismatch(
                    f"collection {self.collection_name} has vector size "
                    f"{current_size}, expected {vector_size}"
                )
            return
        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=qmodels.VectorParams(
                size=vector_size,
                distance=qmodels.Distance.COSINE,
            ),
        )
        self._create_payload_indexes()

    def upsert(self, points: Iterable[VectorPoint]) -> None:
        qdrant_points = [
            qmodels.PointStruct(id=point.id, vector=point.vector, payload=point.payload)
            for point in points
        ]
        if not qdrant_points:
            return
        self.client.upsert(collection_name=self.collection_name, points=qdrant_points)

    def delete_points(self, point_ids: Iterable[str]) -> None:
        ids = list(point_ids)
        if not ids:
            return
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=qmodels.PointIdsList(points=ids),
        )

    def delete_by_payload(self, field_name: str, value: Any) -> None:
        if not self._collection_exists():
            return
        query_filter = qmodels.Filter(
            must=[qmodels.FieldCondition(key=field_name, match=qmodels.MatchValue(value=value))]
        )
        selector = (
            qmodels.FilterSelector(filter=query_filter)
            if hasattr(qmodels, "FilterSelector")
            else query_filter
        )
        try:
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=selector,
            )
        except Exception:
            pass

    def search(
        self,
        *,
        vector: list[float],
        query_filter: Any,
        limit: int,
    ) -> list[VectorSearchResult]:
        if limit <= 0:
            return []
        if not self._collection_exists():
            return []
        try:
            if hasattr(self.client, "search"):
                results = self.client.search(
                    collection_name=self.collection_name,
                    query_vector=vector,
                    query_filter=query_filter,
                    limit=limit,
                    with_payload=True,
                )
            else:
                response = self.client.query_points(
                    collection_name=self.collection_name,
                    query=vector,
                    query_filter=query_filter,
                    limit=limit,
                    with_payload=True,
                )
                results = response.points
        except (UnexpectedResponse, ValueError, Exception):
            return []
        return [
            VectorSearchResult(
                id=str(item.id),
                score=float(item.score),
                payload=dict(item.payload or {}),
            )
            for item in results
        ]

    def _collection_exists(self) -> bool:
        if hasattr(self.client, "collection_exists"):
            try:
                return bool(self.client.collection_exists(self.collection_name))
            except Exception:
                return False
        try:
            self.client.get_collection(self.collection_name)
            return True
        except (UnexpectedResponse, ValueError, Exception):
            return False

    def _collection_vector_size(self) -> int | None:
        collection = self.client.get_collection(self.collection_name)
        config = collection.config.params.vectors
        if hasattr(config, "size"):
            return int(config.size)
        if isinstance(config, dict) and "" in config and hasattr(config[""], "size"):
            return int(config[""].size)
        return None

    def _create_payload_indexes(self) -> None:
        for field in (
            "organization_id",
            "workspace_id",
            "document_id",
            "version_id",
            "chunk_id",
            "source_type",
            "language",
            "is_current",
        ):
            self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name=field,
                field_schema=qmodels.PayloadSchemaType.KEYWORD,
            )
