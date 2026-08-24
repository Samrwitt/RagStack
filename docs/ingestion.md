# Ingestion

Status: **Phase 4 implemented** (fetch through normalize and duplicate recording). Chunking starts in Phase 5.

## Goals

1. Collect from heterogeneous sources through one connector protocol.
2. Store **raw bytes** before any parse so jobs are replayable.
3. Identify documents **stably** so re-discovery is an upsert, not a duplicate.
4. Skip work when the SHA-256 content hash is unchanged.
5. Version documents when the hash changes; only current versions are searchable later.
6. Drive a visible state machine from `DISCOVERED` through `INDEXED`.
7. Parse into structured blocks (not a flattened string) before later stages.
8. Propagate deletes through chunks and vector points (vector cleanup is Phase 6/7).

## What Phase 2–3 do

```text
upload / discover
  → stable document ID
  → SHA-256 of original bytes
  → unchanged? SKIPPED_UNCHANGED (no new version)
  → changed? store raw/vN, version += 1, state FETCHED
  → PARSING → PARSED (structured blocks)
  → NORMALIZING → NORMALIZED (clean text, language, duplicates)
```

Identical bytes at submit time never enqueue a worker. A **reprocess** job replays stored raw and re-parses even when the hash is unchanged (parser upgrades).

## Connector protocol

```python
class SourceConnector(Protocol):
    async def discover(self, checkpoint=None): ...
    async def fetch(self, source_id: str): ...
    async def get_permissions(self, source_id: str): ...
    async def checkpoint(self): ...
```

Connectors emit a **canonical document**. Downstream stages must not branch on source type.

Phase 2 connector: **local file upload** (PDF, TXT, Markdown, HTML, DOCX).
Phase 10: website, GitHub, PostgreSQL, REST API.

## Identity and hashing

Stable IDs are UUID5 over:

```text
organization_id | source | source_connection_id | source_id
```

For uploads, `source_id` is the normalized filename (or a client-supplied identifier). Re-uploading `employee-handbook.txt` always maps to the same document row.

Content hashing uses SHA-256 over **original bytes**. Equal hash → job status `SKIPPED_UNCHANGED`, no parse/chunk/embed. Changed hash → `version += 1` and a new raw object.

## Raw object layout

```text
raw/<source>/<document-id>/v<version>/<filename>
staging/<organization-id>/<job-id>/original
```

Staging holds bytes until the worker writes the versioned raw key. See `app.core.storage.raw_object_key`.

## State machine

```text
DISCOVERED → FETCHING → FETCHED → PARSING → PARSED → NORMALIZING
  → NORMALIZED → CHUNKING → CHUNKED → EMBEDDING → EMBEDDED
  → INDEXING → INDEXED
FAILED | DELETED
```

`UNCHANGED` is a **job outcome**, not a document state. The document stays at its last successful state (typically `PARSED` after Phase 3).

`PARSED → PARSING` is allowed so a reprocess can upgrade parser output without pretending to re-fetch.

Each document stores `current_state`, `last_successful_state`, `last_error`, `retry_count`, `updated_at`.

Parse failures are classified:

- **permanent** (`unsupported MIME`, corrupt file, scanned PDF with no OCR recovery) — Celery does not retry
- **temporary** (storage/network) — exponential backoff

## Jobs and idempotency

In-flight work is keyed by `upload:{connection}:{source_id}:{hash}` so duplicate submits while a job is queued coalesce. Historical skip/success jobs are retained for the audit trail.

Retry: `POST /api/v1/jobs/{id}/retry`. Reprocess from stored raw (no re-fetch): `POST /api/v1/documents/{id}/reprocess`.

## How to run

```bash
docker compose up --build
curl -s http://localhost:8000/api/v1/sources

curl -F "file=@handbook.md;filename=employee-handbook.md;type=text/markdown" \
  http://localhost:8000/api/v1/documents/upload

# identical bytes → unchanged: true, status SKIPPED_UNCHANGED
# edited bytes → new version, previous is_current=false, state PARSED

curl -s http://localhost:8000/api/v1/documents/{id}/blocks
```

Omit `X-Organization-Id` in development; the API bootstraps the Acme Systems tenant.

See [parsing.md](parsing.md) for parser versioning, block types, and OCR policy.

See [normalization.md](normalization.md) for cleaning, language, and duplicate policy.
