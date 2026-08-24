# Ingestion

Status: **designed**. Control-plane implementation begins in Phase 2. Phase 1 provides the processes (API, Celery, PostgreSQL, MinIO) that ingestion will use.

## Goals

1. Collect from heterogeneous sources through one connector protocol.
2. Store **raw bytes** before any parse so jobs are replayable.
3. Identify documents **stably** so re-discovery is an upsert, not a duplicate.
4. Skip work when the SHA-256 content hash is unchanged.
5. Version documents when the hash changes; only current versions are searchable.
6. Drive a visible state machine from `DISCOVERED` through `INDEXED`.
7. Propagate deletes through chunks and vector points.

## Connector protocol (Phase 2+)

```python
class SourceConnector(Protocol):
    async def discover(self, checkpoint=None): ...
    async def fetch(self, source_id: str): ...
    async def get_permissions(self, source_id: str): ...
    async def checkpoint(self): ...
```

Connectors emit a **canonical document**. Downstream stages must not branch on "this came from GitHub."

Planned connectors: local upload, website crawler, GitHub, PostgreSQL (cursor/CDC-ready), REST API. Google Drive is optional.

## Identity and hashing

Stable IDs are derived from `organization + source + source_connection + source_id`. Content hashing uses SHA-256 over normalized raw bytes. Equal hash → `UNCHANGED` and skip parse/chunk/embed/index. Changed hash → `version += 1`.

## Raw object layout

```text
raw/<source>/<document-id>/v<version>/<filename>
```

MinIO (local) and S3 (production) share this key scheme. See `app.core.storage.raw_object_key`.

## State machine

```text
DISCOVERED → FETCHING → FETCHED → PARSING → PARSED → NORMALIZING
  → NORMALIZED → CHUNKING → CHUNKED → EMBEDDING → EMBEDDED
  → INDEXING → INDEXED
FAILED | DELETED
```

Each document stores `current_state`, `last_successful_state`, `last_error`, `retry_count`, `updated_at`. Temporary failures retry with backoff; permanent failures go to a DLQ (Phase 13).

## Checkpoints and backpressure

Connectors persist cursors (`updated_at`, pagination, GitHub cursors, crawl timestamps). Celery queues are split (`ingestion`, `embedding`, `indexing`) with `worker_prefetch_multiplier=1` so collectors cannot flood embedders.
