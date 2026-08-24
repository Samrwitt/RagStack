"""GitHub connector for repository files, issues, and pull requests."""

from __future__ import annotations

import base64
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import httpx

from app.connectors.base import metadata_with_connector, permissions_from_config
from app.connectors.protocol import ConnectorPermission, DiscoveredItem, FetchedContent


class GitHubConnector:
    def __init__(self, *, config: dict[str, Any]) -> None:
        self.config = config
        self.owner = str(config["owner"])
        self.repo = str(config["repo"])
        self.branch = str(config.get("branch", "main"))
        self.include_issues = bool(config.get("include_issues", True))
        self.include_pull_requests = bool(config.get("include_pull_requests", True))
        self.include_paths = [str(item) for item in config.get("include_paths", [""])]
        self.api_base = str(config.get("api_base", "https://api.github.com")).rstrip("/")
        self._items: dict[str, dict[str, Any]] = {}
        self._checkpoint: dict[str, Any] = {}

    async def discover(
        self,
        checkpoint: dict[str, Any] | None = None,
    ) -> AsyncIterator[DiscoveredItem]:
        del checkpoint
        timeout = float(self.config.get("timeout_seconds", 30))
        async with httpx.AsyncClient(timeout=timeout) as client:
            for path in self.include_paths:
                async for item in self._discover_tree(client, path):
                    yield item
            if self.include_issues:
                async for item in self._discover_items(client, kind="issues"):
                    yield item
            if self.include_pull_requests:
                async for item in self._discover_items(client, kind="pulls"):
                    yield item
        self._checkpoint = {"last_sync_at": datetime.now(UTC).isoformat()}

    async def fetch(self, source_id: str) -> FetchedContent:
        item = self._items[source_id]
        if item["kind"] == "file":
            data = await self._fetch_file(item)
            mime_type = _mime_for_path(item["path"])
        else:
            data = _markdown_record(item).encode("utf-8")
            mime_type = "text/markdown"
        return FetchedContent(
            source_id=source_id,
            title=item["title"],
            mime_type=mime_type,
            data=data,
            source_url=item.get("html_url"),
            metadata=metadata_with_connector("github", item),
            permissions=await self.get_permissions(source_id),
            retrieved_at=datetime.now(UTC),
        )

    async def get_permissions(self, source_id: str) -> ConnectorPermission:
        del source_id
        return permissions_from_config(self.config)

    async def checkpoint(self) -> dict[str, Any]:
        return self._checkpoint

    async def _discover_tree(
        self,
        client: httpx.AsyncClient,
        path: str,
    ) -> AsyncIterator[DiscoveredItem]:
        url = f"{self.api_base}/repos/{self.owner}/{self.repo}/contents/{path}"
        response = await client.get(url, params={"ref": self.branch}, headers=self._headers())
        response.raise_for_status()
        payload = response.json()
        entries = payload if isinstance(payload, list) else [payload]
        for entry in entries:
            if entry.get("type") == "dir":
                async for item in self._discover_tree(client, str(entry["path"])):
                    yield item
                continue
            if entry.get("type") != "file":
                continue
            source_id = f"github:file:{self.owner}/{self.repo}/{entry['path']}"
            record = {
                "kind": "file",
                "path": entry["path"],
                "sha": entry.get("sha"),
                "title": entry["name"],
                "download_url": entry.get("download_url"),
                "html_url": entry.get("html_url"),
            }
            self._items[source_id] = record
            yield DiscoveredItem(
                source_id=source_id,
                title=record["title"],
                mime_type=_mime_for_path(record["path"]),
                source_url=record.get("html_url"),
                metadata=metadata_with_connector("github", record),
            )

    async def _discover_items(
        self,
        client: httpx.AsyncClient,
        *,
        kind: str,
    ) -> AsyncIterator[DiscoveredItem]:
        page = 1
        while True:
            response = await client.get(
                f"{self.api_base}/repos/{self.owner}/{self.repo}/{kind}",
                params={"state": "all", "per_page": 100, "page": page},
                headers=self._headers(),
            )
            response.raise_for_status()
            rows = response.json()
            if not rows:
                break
            for row in rows:
                source_id = f"github:{kind}:{self.owner}/{self.repo}/{row['number']}"
                record = {
                    "kind": kind,
                    "number": row["number"],
                    "title": row.get("title") or source_id,
                    "body": row.get("body") or "",
                    "state": row.get("state"),
                    "html_url": row.get("html_url"),
                    "updated_at": row.get("updated_at"),
                }
                self._items[source_id] = record
                yield DiscoveredItem(
                    source_id=source_id,
                    title=record["title"],
                    mime_type="text/markdown",
                    source_url=record.get("html_url"),
                    updated_at=_parse_datetime(record.get("updated_at")),
                    metadata=metadata_with_connector("github", record),
                )
            page += 1

    async def _fetch_file(self, item: dict[str, Any]) -> bytes:
        timeout = float(self.config.get("timeout_seconds", 30))
        if item.get("download_url"):
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(str(item["download_url"]), headers=self._headers())
                response.raise_for_status()
                return response.content
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(
                f"{self.api_base}/repos/{self.owner}/{self.repo}/contents/{item['path']}",
                params={"ref": self.branch},
                headers=self._headers(),
            )
            response.raise_for_status()
            payload = response.json()
            return base64.b64decode(str(payload["content"]))

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/vnd.github+json"}
        token = self.config.get("token")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers


def _markdown_record(item: dict[str, Any]) -> str:
    return f"# {item['title']}\n\nState: {item.get('state', 'unknown')}\n\n{item.get('body', '')}"


def _mime_for_path(path: str) -> str:
    lowered = path.lower()
    if lowered.endswith(".md") or lowered.endswith(".markdown"):
        return "text/markdown"
    if lowered.endswith(".html") or lowered.endswith(".htm"):
        return "text/html"
    return "text/plain"


def _parse_datetime(value: object) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
