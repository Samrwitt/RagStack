"""Connector sync orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.connectors.registry import build_connector
from app.ingestion.service import IngestOutcome, IngestionService
from app.models.enums import SourceStatus
from app.models.source import SourceConnection


@dataclass(slots=True)
class ConnectorSyncOutcome:
    source_id: UUID
    discovered: int = 0
    fetched: int = 0
    queued: int = 0
    skipped: int = 0
    deleted: int = 0
    ingestion_jobs: list[IngestOutcome] = field(default_factory=list)
    checkpoint: dict = field(default_factory=dict)


class ConnectorSyncService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.ingestion = IngestionService(session)

    async def sync_source(
        self,
        *,
        organization_id: UUID,
        source_connection_id: UUID,
        limit: int | None = None,
    ) -> ConnectorSyncOutcome:
        source = self.ingestion.get_source(organization_id, source_connection_id)
        connector = build_connector(source)
        outcome = ConnectorSyncOutcome(source_id=source.id)
        async for item in connector.discover(source.checkpoint):
            if limit is not None and outcome.discovered >= limit:
                break
            outcome.discovered += 1
            if item.deleted:
                outcome.deleted += 1
                continue
            content = await connector.fetch(item.source_id)
            outcome.fetched += 1
            submitted = self.ingestion.submit_connector_content(
                organization_id=organization_id,
                source_connection_id=source.id,
                content=content,
            )
            outcome.ingestion_jobs.append(submitted)
            if submitted.unchanged:
                outcome.skipped += 1
            elif submitted.enqueue:
                outcome.queued += 1
        checkpoint = await connector.checkpoint()
        self._mark_source_synced(source, checkpoint)
        outcome.checkpoint = checkpoint
        return outcome

    def _mark_source_synced(self, source: SourceConnection, checkpoint: dict) -> None:
        source.checkpoint = checkpoint
        source.last_sync_at = datetime.now(UTC)
        source.last_error = None
        if source.status == SourceStatus.ERROR.value:
            source.status = SourceStatus.CONNECTED.value
