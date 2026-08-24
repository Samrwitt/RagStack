"""Local file-upload connector.

Uploads are already in hand when discover/fetch run. The connector exists so
the ingestion service talks to one protocol, not a special-case upload path.
"""

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from app.connectors.protocol import (
    CanonicalDocument,
    ConnectorPermission,
    DiscoveredItem,
    FetchedContent,
)
from app.ingestion.identity import stable_document_id
from app.models.enums import SourceType


class FileUploadConnector:
    def __init__(
        self,
        *,
        organization_id: UUID,
        source_connection_id: UUID,
        source_id: str,
        title: str,
        mime_type: str,
        data: bytes,
        original_filename: str,
        permissions: ConnectorPermission | None = None,
    ) -> None:
        self._organization_id = organization_id
        self._source_connection_id = source_connection_id
        self._source_id = source_id
        self._title = title
        self._mime_type = mime_type
        self._data = data
        self._original_filename = original_filename
        self._permissions = permissions or ConnectorPermission()
        self._retrieved_at = datetime.now(UTC)

    async def discover(
        self, checkpoint: dict[str, Any] | None = None
    ) -> AsyncIterator[DiscoveredItem]:
        del checkpoint
        yield DiscoveredItem(
            source_id=self._source_id,
            title=self._title,
            mime_type=self._mime_type,
            metadata={"original_filename": self._original_filename},
            updated_at=self._retrieved_at,
        )

    async def fetch(self, source_id: str) -> FetchedContent:
        if source_id != self._source_id:
            raise KeyError(source_id)
        return FetchedContent(
            source_id=self._source_id,
            title=self._title,
            mime_type=self._mime_type,
            data=self._data,
            metadata={"original_filename": self._original_filename},
            permissions=self._permissions,
            retrieved_at=self._retrieved_at,
        )

    async def get_permissions(self, source_id: str) -> ConnectorPermission:
        del source_id
        return self._permissions

    async def checkpoint(self) -> dict[str, Any]:
        return {"last_uploaded_at": self._retrieved_at.isoformat()}

    def to_canonical(self) -> CanonicalDocument:
        return CanonicalDocument(
            document_id=stable_document_id(
                self._organization_id,
                SourceType.FILE_UPLOAD.value,
                self._source_connection_id,
                self._source_id,
            ),
            organization_id=self._organization_id,
            source=SourceType.FILE_UPLOAD.value,
            source_id=self._source_id,
            title=self._title,
            mime_type=self._mime_type,
            content=self._data,
            metadata={"original_filename": self._original_filename},
            permissions={
                "organization_id": str(self._organization_id),
                "allowed_users": self._permissions.allowed_users,
                "allowed_groups": self._permissions.allowed_groups,
            },
            created_at=self._retrieved_at,
            updated_at=self._retrieved_at,
        )
