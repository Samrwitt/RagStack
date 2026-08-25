"""Google Drive connector using Drive API metadata and file export/download."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import httpx

from app.connectors.base import metadata_with_connector, permissions_from_config
from app.connectors.protocol import ConnectorPermission, DiscoveredItem, FetchedContent

GOOGLE_DOC_EXPORTS = {
    "application/vnd.google-apps.document": ("text/markdown", "text/markdown"),
    "application/vnd.google-apps.spreadsheet": ("text/csv", "text/csv"),
    "application/vnd.google-apps.presentation": ("text/plain", "text/plain"),
}


class GoogleDriveConnector:
    def __init__(self, *, config: dict[str, Any]) -> None:
        self.config = config
        self.api_base = str(config.get("api_base", "https://www.googleapis.com/drive/v3")).rstrip("/")
        self.folder_id = config.get("folder_id")
        self._files: dict[str, dict[str, Any]] = {}
        self._checkpoint: dict[str, Any] = {}

    async def discover(
        self,
        checkpoint: dict[str, Any] | None = None,
    ) -> AsyncIterator[DiscoveredItem]:
        checkpoint = checkpoint or {}
        if checkpoint.get("start_page_token"):
            async for item in self._discover_changes(checkpoint):
                yield item
            return
        async for item in self._discover_full(checkpoint):
            yield item

    async def _discover_full(
        self,
        checkpoint: dict[str, Any],
    ) -> AsyncIterator[DiscoveredItem]:
        page_token = (checkpoint or {}).get("page_token")
        query = "trashed = false"
        if self.folder_id:
            query += f" and '{self.folder_id}' in parents"
        timeout = float(self.config.get("timeout_seconds", 30))
        async with httpx.AsyncClient(timeout=timeout) as client:
            while True:
                params = {
                    "q": query,
                    "fields": "nextPageToken,files(id,name,mimeType,webViewLink,modifiedTime)",
                    "pageSize": int(self.config.get("page_size", 100)),
                    "supportsAllDrives": True,
                    "includeItemsFromAllDrives": True,
                }
                if page_token:
                    params["pageToken"] = page_token
                response = await client.get(
                    f"{self.api_base}/files",
                    params=params,
                    headers=self._headers(),
                )
                if getattr(response, "status_code", None) == 410:
                    async for item in self._discover_full({}):
                        yield item
                    return
                response.raise_for_status()
                payload = response.json()
                for file in payload.get("files", []):
                    source_id = str(file["id"])
                    self._files[source_id] = file
                    mime_type = _export_mime(file["mimeType"])
                    yield DiscoveredItem(
                        source_id=source_id,
                        title=str(file.get("name") or source_id),
                        mime_type=mime_type,
                        source_url=file.get("webViewLink"),
                        updated_at=_parse_datetime(file.get("modifiedTime")),
                        metadata=metadata_with_connector("google_drive", file),
                    )
                page_token = payload.get("nextPageToken")
                self._checkpoint = {
                    "page_token": page_token,
                    "last_sync_at": datetime.now(UTC).isoformat(),
                }
                if not page_token:
                    break
            self._checkpoint["start_page_token"] = await self._start_page_token(client)

    async def _discover_changes(
        self,
        checkpoint: dict[str, Any],
    ) -> AsyncIterator[DiscoveredItem]:
        page_token = str(checkpoint["start_page_token"])
        timeout = float(self.config.get("timeout_seconds", 30))
        async with httpx.AsyncClient(timeout=timeout) as client:
            while page_token:
                response = await client.get(
                    f"{self.api_base}/changes",
                    params={
                        "pageToken": page_token,
                        "fields": (
                            "nextPageToken,newStartPageToken,"
                            "changes(fileId,removed,file(id,name,mimeType,webViewLink,"
                            "modifiedTime,trashed,parents))"
                        ),
                        "pageSize": int(self.config.get("page_size", 100)),
                        "includeRemoved": True,
                        "supportsAllDrives": True,
                        "includeItemsFromAllDrives": True,
                    },
                    headers=self._headers(),
                )
                response.raise_for_status()
                payload = response.json()
                for change in payload.get("changes", []):
                    file_id = str(change.get("fileId"))
                    file = change.get("file") or {}
                    if change.get("removed") or file.get("trashed"):
                        yield DiscoveredItem(
                            source_id=file_id,
                            title=file_id,
                            deleted=True,
                            metadata=metadata_with_connector("google_drive", change),
                        )
                        continue
                    if self.folder_id and self.folder_id not in set(file.get("parents") or []):
                        continue
                    source_id = str(file["id"])
                    self._files[source_id] = file
                    yield DiscoveredItem(
                        source_id=source_id,
                        title=str(file.get("name") or source_id),
                        mime_type=_export_mime(file["mimeType"]),
                        source_url=file.get("webViewLink"),
                        updated_at=_parse_datetime(file.get("modifiedTime")),
                        metadata=metadata_with_connector("google_drive", file),
                    )
                page_token = payload.get("nextPageToken")
                if payload.get("newStartPageToken"):
                    self._checkpoint = {
                        "start_page_token": payload["newStartPageToken"],
                        "last_sync_at": datetime.now(UTC).isoformat(),
                    }

    async def fetch(self, source_id: str) -> FetchedContent:
        file = self._files[source_id]
        mime_type = str(file["mimeType"])
        timeout = float(self.config.get("timeout_seconds", 30))
        async with httpx.AsyncClient(timeout=timeout) as client:
            if mime_type in GOOGLE_DOC_EXPORTS:
                export_mime, stored_mime = GOOGLE_DOC_EXPORTS[mime_type]
                url = f"{self.api_base}/files/{source_id}/export"
                response = await client.get(
                    url,
                    params={"mimeType": export_mime},
                    headers=self._headers(),
                )
                final_mime = stored_mime
            else:
                url = f"{self.api_base}/files/{source_id}"
                response = await client.get(url, params={"alt": "media"}, headers=self._headers())
                final_mime = mime_type
            response.raise_for_status()
        return FetchedContent(
            source_id=source_id,
            title=str(file.get("name") or source_id),
            mime_type=final_mime,
            data=response.content,
            source_url=file.get("webViewLink"),
            metadata=metadata_with_connector("google_drive", file),
            permissions=await self.get_permissions(source_id),
            retrieved_at=datetime.now(UTC),
        )

    async def get_permissions(self, source_id: str) -> ConnectorPermission:
        timeout = float(self.config.get("timeout_seconds", 30))
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(
                f"{self.api_base}/files/{source_id}/permissions",
                params={
                    "fields": "permissions(type,emailAddress,domain,role,deleted)",
                    "supportsAllDrives": True,
                },
                headers=self._headers(),
            )
            response.raise_for_status()
        upstream = response.json().get("permissions", [])
        users: set[str] = set()
        groups: set[str] = set()
        for item in upstream:
            if item.get("deleted") or item.get("role") == "owner":
                continue
            permission_type = item.get("type")
            email = item.get("emailAddress")
            domain = item.get("domain")
            if permission_type == "user" and email:
                users.add(str(email).lower())
            elif permission_type == "group" and email:
                groups.add(str(email).lower())
            elif permission_type == "domain" and domain:
                groups.add(f"domain:{str(domain).lower()}")
            elif permission_type == "anyone":
                return ConnectorPermission()
        fallback = permissions_from_config(self.config)
        return ConnectorPermission(
            allowed_users=sorted({*fallback.allowed_users, *users}),
            allowed_groups=sorted({*fallback.allowed_groups, *groups}),
        )

    async def checkpoint(self) -> dict[str, Any]:
        return self._checkpoint

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.config['access_token']}"}

    async def _start_page_token(self, client: httpx.AsyncClient) -> str:
        response = await client.get(
            f"{self.api_base}/changes/startPageToken",
            params={"supportsAllDrives": True},
            headers=self._headers(),
        )
        response.raise_for_status()
        return str(response.json()["startPageToken"])


def _export_mime(mime_type: str) -> str:
    return GOOGLE_DOC_EXPORTS.get(mime_type, (mime_type, mime_type))[1]


def _parse_datetime(value: object) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
