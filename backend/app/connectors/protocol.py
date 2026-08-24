"""Shared source connector contract.

Every connector discovers upstream items, fetches bytes, reports ACLs, and
persists a checkpoint so a crashed worker resumes instead of restarting.
"""

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID


@dataclass(slots=True)
class ConnectorPermission:
    allowed_users: list[str] = field(default_factory=list)
    allowed_groups: list[str] = field(default_factory=list)


@dataclass(slots=True)
class DiscoveredItem:
    source_id: str
    title: str
    mime_type: str | None = None
    source_url: str | None = None
    updated_at: datetime | None = None
    deleted: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class FetchedContent:
    source_id: str
    title: str
    mime_type: str
    data: bytes
    source_url: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    permissions: ConnectorPermission = field(default_factory=ConnectorPermission)
    retrieved_at: datetime | None = None


@dataclass(slots=True)
class CanonicalDocument:
    """Source-agnostic document handed to the rest of the pipeline."""

    document_id: UUID
    organization_id: UUID
    source: str
    source_id: str
    title: str
    mime_type: str
    content: bytes
    source_url: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    permissions: dict[str, Any] = field(default_factory=dict)


class SourceConnector(Protocol):
    async def discover(
        self, checkpoint: dict[str, Any] | None = None
    ) -> AsyncIterator[DiscoveredItem]: ...

    async def fetch(self, source_id: str) -> FetchedContent: ...

    async def get_permissions(self, source_id: str) -> ConnectorPermission: ...

    async def checkpoint(self) -> dict[str, Any]: ...


class ConnectorError(RuntimeError):
    """Base class for connector failures."""


class ConnectorConfigurationError(ConnectorError):
    """Raised when a source config cannot construct a connector."""


class ConnectorRateLimitError(ConnectorError):
    """Raised when an upstream connector is rate limited."""
