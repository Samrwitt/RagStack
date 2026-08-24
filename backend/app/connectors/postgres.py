"""PostgreSQL table/view connector with primary-key checkpoints."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from app.connectors.base import metadata_with_connector, permissions_from_config
from app.connectors.protocol import ConnectorConfigurationError, ConnectorPermission, DiscoveredItem, FetchedContent


class PostgresConnector:
    def __init__(self, *, config: dict[str, Any]) -> None:
        self.config = config
        self.dsn = str(config["dsn"])
        self.table = str(config["table"])
        self.pk_field = str(config.get("pk_field", "id"))
        self.title_field = str(config.get("title_field", self.pk_field))
        self.content_fields = [str(item) for item in config.get("content_fields", [])]
        self.updated_at_field = str(config.get("updated_at_field", "updated_at"))
        self.batch_size = int(config.get("batch_size", 500))
        self._rows: dict[str, dict[str, Any]] = {}
        self._checkpoint: dict[str, Any] = {}

    async def discover(
        self,
        checkpoint: dict[str, Any] | None = None,
    ) -> AsyncIterator[DiscoveredItem]:
        psycopg = _load_psycopg()
        last_pk = (checkpoint or {}).get("last_pk")
        query = self._query(last_pk)
        with psycopg.connect(self.dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(query)
                columns = [desc.name for desc in cur.description]
                for raw in cur.fetchall():
                    row = dict(zip(columns, raw, strict=True))
                    source_id = str(row[self.pk_field])
                    self._rows[source_id] = row
                    self._checkpoint = {
                        "last_pk": source_id,
                        "last_sync_at": datetime.now(UTC).isoformat(),
                    }
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

    def _query(self, last_pk: object) -> str:
        safe_table = _safe_identifier(self.table)
        safe_pk = _safe_identifier(self.pk_field)
        columns = sorted({self.pk_field, self.title_field, self.updated_at_field, *self.content_fields})
        selected = ", ".join(_safe_identifier(column) for column in columns)
        where = f" WHERE {safe_pk} > {json.dumps(last_pk)}" if last_pk is not None else ""
        return f"SELECT {selected} FROM {safe_table}{where} ORDER BY {safe_pk} LIMIT {self.batch_size}"


def _load_psycopg():
    try:
        import psycopg
    except ModuleNotFoundError as exc:
        raise ConnectorConfigurationError("psycopg is required for postgres connector") from exc
    return psycopg


def _safe_identifier(value: str) -> str:
    if not value.replace("_", "").replace(".", "").isalnum():
        raise ConnectorConfigurationError(f"unsafe SQL identifier: {value}")
    return ".".join(f'"{part}"' for part in value.split("."))


def _parse_datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value
    return None
