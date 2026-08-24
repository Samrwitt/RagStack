"""Generic REST API connector with pagination and cursor checkpoints."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import httpx

from app.connectors.base import metadata_with_connector, permissions_from_config
from app.connectors.protocol import ConnectorPermission, DiscoveredItem, FetchedContent


class RestApiConnector:
    def __init__(self, *, config: dict[str, Any]) -> None:
        self.config = config
        self.base_url = str(config["base_url"]).rstrip("/")
        self.items_path = str(config.get("items_path", ""))
        self.content_field = str(config.get("content_field", "content"))
        self.id_field = str(config.get("id_field", "id"))
        self.title_field = str(config.get("title_field", "title"))
        self.url_field = str(config.get("url_field", "url"))
        self.updated_at_field = str(config.get("updated_at_field", "updated_at"))
        self.deleted_field = str(config.get("deleted_field", "deleted"))
        self.next_cursor_field = str(config.get("next_cursor_field", "next_cursor"))
        self.cursor_param = str(config.get("cursor_param", "cursor"))
        self.items_field = str(config.get("items_field", "items"))
        self.mime_type = str(config.get("mime_type", "application/json"))
        self._checkpoint: dict[str, Any] = {}
        self._items: dict[str, dict[str, Any]] = {}

    async def discover(
        self,
        checkpoint: dict[str, Any] | None = None,
    ) -> AsyncIterator[DiscoveredItem]:
        cursor = (checkpoint or {}).get("cursor")
        headers = self._headers()
        timeout = float(self.config.get("timeout_seconds", 30))
        async with httpx.AsyncClient(timeout=timeout) as client:
            while True:
                params = dict(self.config.get("params", {}))
                if cursor:
                    params[self.cursor_param] = cursor
                response = await client.get(
                    f"{self.base_url}/{self.items_path.lstrip('/')}",
                    params=params,
                    headers=headers,
                )
                response.raise_for_status()
                payload = response.json()
                items = payload.get(self.items_field, payload if isinstance(payload, list) else [])
                for item in items:
                    source_id = str(item[self.id_field])
                    self._items[source_id] = item
                    yield DiscoveredItem(
                        source_id=source_id,
                        title=str(item.get(self.title_field) or source_id),
                        mime_type=self.mime_type,
                        source_url=item.get(self.url_field),
                        updated_at=_parse_datetime(item.get(self.updated_at_field)),
                        deleted=bool(item.get(self.deleted_field, False)),
                        metadata=metadata_with_connector("rest_api", {"raw": item}),
                    )
                cursor = payload.get(self.next_cursor_field) if isinstance(payload, dict) else None
                self._checkpoint = {"cursor": cursor, "last_sync_at": datetime.now(UTC).isoformat()}
                if not cursor:
                    break

    async def fetch(self, source_id: str) -> FetchedContent:
        item = self._items[source_id]
        content = item.get(self.content_field, item)
        data = (
            content.encode("utf-8")
            if isinstance(content, str)
            else json.dumps(content, sort_keys=True).encode("utf-8")
        )
        return FetchedContent(
            source_id=source_id,
            title=str(item.get(self.title_field) or source_id),
            mime_type=self.mime_type,
            data=data,
            source_url=item.get(self.url_field),
            metadata=metadata_with_connector("rest_api", {"raw": item}),
            permissions=await self.get_permissions(source_id),
            retrieved_at=datetime.now(UTC),
        )

    async def get_permissions(self, source_id: str) -> ConnectorPermission:
        del source_id
        return permissions_from_config(self.config)

    async def checkpoint(self) -> dict[str, Any]:
        return self._checkpoint

    def _headers(self) -> dict[str, str]:
        headers = {str(k): str(v) for k, v in self.config.get("headers", {}).items()}
        token = self.config.get("bearer_token")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers


def _parse_datetime(value: object) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
