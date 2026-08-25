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
        checkpoint = checkpoint or {}
        timeout = float(self.config.get("timeout_seconds", 30))
        async with httpx.AsyncClient(timeout=timeout) as client:
            async for item in self._discover_tree(client, checkpoint):
                yield item
            if self.include_issues:
                async for item in self._discover_items(
                    client,
                    kind="issues",
                    checkpoint=checkpoint,
                ):
                    yield item
            if self.include_pull_requests:
                async for item in self._discover_items(
                    client,
                    kind="pulls",
                    checkpoint=checkpoint,
                ):
                    yield item
        self._checkpoint["last_sync_at"] = datetime.now(UTC).isoformat()

    async def fetch(self, source_id: str) -> FetchedContent:
        if source_id not in self._items:
            parts = source_id.split(":")
            if len(parts) >= 3 and parts[0] == "github":
                kind = parts[1]
                rest = ":".join(parts[2:])
                if kind == "file":
                    # rest format: owner/repo/path
                    repo_prefix = f"{self.owner}/{self.repo}/"
                    path = rest[len(repo_prefix):] if rest.startswith(repo_prefix) else rest
                    record = {
                        "kind": "file",
                        "path": path,
                        "title": path.rsplit("/", 1)[-1],
                        "html_url": f"https://github.com/{self.owner}/{self.repo}/blob/{self.branch}/{path}",
                    }
                    self._items[source_id] = record
                elif kind in {"issues", "pulls"}:
                    # rest format: owner/repo/number
                    number = rest.rsplit("/", 1)[-1]
                    timeout = float(self.config.get("timeout_seconds", 30))
                    async with httpx.AsyncClient(timeout=timeout) as client:
                        resp = await client.get(
                            f"{self.api_base}/repos/{self.owner}/{self.repo}/{kind}/{number}",
                            headers=self._headers(),
                        )
                        resp.raise_for_status()
                        row = resp.json()
                        record = {
                            "kind": kind,
                            "number": row.get("number"),
                            "title": row.get("title") or source_id,
                            "body": row.get("body") or "",
                            "state": row.get("state"),
                            "html_url": row.get("html_url"),
                            "updated_at": row.get("updated_at"),
                        }
                        self._items[source_id] = record

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
        checkpoint: dict[str, Any],
    ) -> AsyncIterator[DiscoveredItem]:
        response = await client.get(
            f"{self.api_base}/repos/{self.owner}/{self.repo}/git/trees/{self.branch}",
            params={"recursive": "1"},
            headers=self._headers(),
        )
        response.raise_for_status()
        payload = response.json()
        previous = dict((checkpoint.get("files") or {}).get("shas") or {})
        current: dict[str, str] = {}
        truncated = bool(payload.get("truncated"))
        for entry in payload.get("tree", []):
            if entry.get("type") != "blob":
                continue
            path = str(entry["path"])
            if not self._path_included(path):
                continue
            sha = str(entry.get("sha") or "")
            current[path] = sha
            if previous.get(path) == sha:
                continue
            source_id = f"github:file:{self.owner}/{self.repo}/{entry['path']}"
            record = {
                "kind": "file",
                "path": path,
                "sha": sha,
                "title": path.rsplit("/", 1)[-1],
                "download_url": None,
                "html_url": (
                    f"https://github.com/{self.owner}/{self.repo}/blob/"
                    f"{self.branch}/{path}"
                ),
            }
            self._items[source_id] = record
            yield DiscoveredItem(
                source_id=source_id,
                title=record["title"],
                mime_type=_mime_for_path(record["path"]),
                source_url=record.get("html_url"),
                metadata=metadata_with_connector("github", record),
            )
        if not truncated:
            for path in sorted(set(previous) - set(current)):
                yield DiscoveredItem(
                    source_id=f"github:file:{self.owner}/{self.repo}/{path}",
                    title=path.rsplit("/", 1)[-1] or path,
                    deleted=True,
                    metadata=metadata_with_connector(
                        "github",
                        {"kind": "file", "path": path, "deleted": True},
                    ),
                )
        self._checkpoint["files"] = {
            "tree_sha": payload.get("sha"),
            "truncated": truncated,
            "shas": previous if truncated else current,
        }

    async def _discover_items(
        self,
        client: httpx.AsyncClient,
        *,
        kind: str,
        checkpoint: dict[str, Any],
    ) -> AsyncIterator[DiscoveredItem]:
        page = 1
        cursor_key = f"{kind}_updated_at"
        since = checkpoint.get(cursor_key)
        latest = since
        stop_paging = False
        while not stop_paging:
            params: dict[str, Any] = {
                "state": "all",
                "per_page": 100,
                "page": page,
                "sort": "updated",
                "direction": "desc",
            }
            if kind == "issues" and since:
                params["since"] = since
            response = await client.get(
                f"{self.api_base}/repos/{self.owner}/{self.repo}/{kind}",
                params=params,
                headers=self._headers(),
            )
            response.raise_for_status()
            rows = response.json()
            if not rows:
                break
            for row in rows:
                updated_at_str = str(row.get("updated_at") or "")
                if since and updated_at_str and updated_at_str <= str(since):
                    stop_paging = True
                    break
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
                if record.get("updated_at") and (
                    latest is None or str(record["updated_at"]) > str(latest)
                ):
                    latest = record["updated_at"]
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
        if latest:
            self._checkpoint[cursor_key] = latest

    def _path_included(self, path: str) -> bool:
        if not self.include_paths or "" in self.include_paths:
            return True
        normalized = path.strip("/")
        for include_path in self.include_paths:
            prefix = include_path.strip("/")
            if normalized == prefix or normalized.startswith(f"{prefix}/"):
                return True
        return False

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
