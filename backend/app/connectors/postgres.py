"""PostgreSQL table/view connector with update-aware checkpoints."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from app.connectors.base import metadata_with_connector, permissions_from_config
from app.connectors.protocol import (
    ConnectorConfigurationError,
    ConnectorPermission,
    DiscoveredItem,
    FetchedContent,
)


class PostgresConnector:
    def __init__(self, *, config: dict[str, Any]) -> None:
        self.config = config
        self.dsn = str(config["dsn"])
        self.table = str(config["table"])
        self.pk_field = str(config.get("pk_field", "id"))
        self.title_field = str(config.get("title_field", self.pk_field))
        self.content_fields = [str(item) for item in config.get("content_fields", [])]
        self.updated_at_field = str(config.get("updated_at_field", "updated_at"))
        self.deleted_field = (
            str(config["deleted_field"]) if config.get("deleted_field") else None
        )
        self.batch_size = int(config.get("batch_size", 500))
        self._rows: dict[str, dict[str, Any]] = {}
        self._checkpoint: dict[str, Any] = {}

    async def discover(
        self,
        checkpoint: dict[str, Any] | None = None,
    ) -> AsyncIterator[DiscoveredItem]:
        psycopg = _load_psycopg()
        query, params = self._query(checkpoint or {})
        with psycopg.connect(self.dsn) as conn, conn.cursor() as cur:
            cur.execute(query, params)
            columns = [desc.name for desc in cur.description]
            for raw in cur.fetchall():
                row = dict(zip(columns, raw, strict=True))
                source_id = str(row[self.pk_field])
                self._checkpoint = {
                    "cursor": _cursor_from_row(row, self.pk_field, self.updated_at_field),
                    "last_sync_at": datetime.now(UTC).isoformat(),
                }
                if self.deleted_field and bool(row.get(self.deleted_field)):
                    yield DiscoveredItem(
                        source_id=source_id,
                        title=str(row.get(self.title_field) or source_id),
                        deleted=True,
                        updated_at=_parse_datetime(row.get(self.updated_at_field)),
                        metadata=metadata_with_connector(
                            "postgres",
                            {
                                "table": self.table,
                                "pk_field": self.pk_field,
                                "deleted_field": self.deleted_field,
                            },
                        ),
                    )
                    continue
                self._rows[source_id] = row
                yield DiscoveredItem(
                    source_id=source_id,
                    title=str(row.get(self.title_field) or source_id),
                    mime_type="application/json",
                    updated_at=_parse_datetime(row.get(self.updated_at_field)),
                    metadata=metadata_with_connector(
                        "postgres",
                        {"table": self.table, "pk_field": self.pk_field},
                    ),
                )

    async def fetch(self, source_id: str) -> FetchedContent:
        row = self._rows[source_id]
        content = (
            {field: row.get(field) for field in self.content_fields}
            if self.content_fields
            else row
        )
        return FetchedContent(
            source_id=source_id,
            title=str(row.get(self.title_field) or source_id),
            mime_type="application/json",
            data=json.dumps(content, default=str, sort_keys=True).encode("utf-8"),
            metadata=metadata_with_connector(
                "postgres",
                {"table": self.table, "pk_field": self.pk_field, "row": row},
            ),
            permissions=await self.get_permissions(source_id),
            retrieved_at=datetime.now(UTC),
        )

    async def get_permissions(self, source_id: str) -> ConnectorPermission:
        del source_id
        return permissions_from_config(self.config)

    async def checkpoint(self) -> dict[str, Any]:
        return self._checkpoint

    def _query(self, checkpoint: dict[str, Any]) -> tuple[Any, list[Any]]:
        psycopg = _load_psycopg()
        sql = psycopg.sql
        field_names = {
            self.pk_field,
            self.title_field,
            self.updated_at_field,
            *self.content_fields,
        }
        if self.deleted_field:
            field_names.add(self.deleted_field)
        columns = sorted(field_names)
        for identifier in [self.table, *columns]:
            _validate_identifier(identifier)
        cursor = checkpoint.get("cursor") if isinstance(checkpoint.get("cursor"), dict) else {}
        updated_at = _parse_checkpoint_datetime(cursor.get("updated_at"))
        pk = cursor.get("pk")
        where = sql.SQL("")
        params: list[Any] = []
        if updated_at is not None and pk is not None:
            where = sql.SQL(
                " WHERE ({updated_at} > %s OR ({updated_at} = %s AND {pk} > %s))"
            ).format(
                updated_at=sql.Identifier(self.updated_at_field),
                pk=sql.Identifier(self.pk_field),
            )
            params.extend([updated_at, updated_at, pk])
        params.append(self.batch_size)
        query = sql.SQL(
            "SELECT {columns} FROM {table}{where} "
            "ORDER BY {updated_at}, {pk} LIMIT %s"
        ).format(
            columns=sql.SQL(", ").join(sql.Identifier(column) for column in columns),
            table=sql.Identifier(*self.table.split(".")),
            where=where,
            updated_at=sql.Identifier(self.updated_at_field),
            pk=sql.Identifier(self.pk_field),
        )
        return query, params


def _load_psycopg():
    try:
        import psycopg
    except ModuleNotFoundError as exc:
        raise ConnectorConfigurationError("psycopg is required for postgres connector") from exc
    return psycopg


def _validate_identifier(value: str) -> None:
    if not value.replace("_", "").replace(".", "").isalnum():
        raise ConnectorConfigurationError(f"unsafe SQL identifier: {value}")


def _parse_datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _parse_checkpoint_datetime(value: object) -> datetime | None:
    parsed = _parse_datetime(value)
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def _cursor_from_row(
    row: dict[str, Any],
    pk_field: str,
    updated_at_field: str,
) -> dict[str, Any]:
    return {
        "updated_at": _json_safe(row.get(updated_at_field)),
        "pk": _json_safe(row.get(pk_field)),
        "pk_type": type(row.get(pk_field)).__name__,
    }


def _json_safe(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    try:
        json.dumps(value)
    except TypeError:
        return str(value)
    return value
