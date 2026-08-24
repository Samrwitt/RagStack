"""Connector helpers shared by network-backed sources."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Iterable
from datetime import UTC, datetime
from typing import Any

from app.connectors.protocol import ConnectorPermission, DiscoveredItem


def utcnow_iso() -> str:
    return datetime.now(UTC).isoformat()


def permissions_from_config(config: dict[str, Any]) -> ConnectorPermission:
    return ConnectorPermission(
        allowed_users=[str(item) for item in config.get("allowed_users", [])],
        allowed_groups=[str(item) for item in config.get("allowed_groups", [])],
    )


def metadata_with_connector(
    connector: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {"connector": connector, **(metadata or {})}


async def iter_with_rate_limit(
    items: Iterable[DiscoveredItem],
    *,
    delay_seconds: float,
) -> AsyncIterator[DiscoveredItem]:
    for item in items:
        if delay_seconds > 0:
            await asyncio.sleep(delay_seconds)
        yield item
