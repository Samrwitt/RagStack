# Connectors

Phase 10 adds connector sync for non-upload sources. A source sync creates an ingestion job, discovers upstream items, fetches changed content, updates the source checkpoint, and enqueues normal ingestion jobs for parse/normalize/chunk/embed/index.

## Supported Sources

| Source type | Config highlights |
| --- | --- |
| `website` | `base_url` or `start_urls`, optional `sitemap_urls`, `max_pages`, `same_domain`, `request_delay_seconds` |
| `github` | `owner`, `repo`, optional `branch`, encrypted `token`, `include_paths`, `include_issues`, `include_pull_requests` |
| `postgres` | encrypted `dsn`, `table`, `pk_field`, `title_field`, `content_fields`, `updated_at_field`, `batch_size` |
| `rest_api` | `base_url`, `items_path`, `id_field`, `title_field`, `content_field`, pagination cursor fields, encrypted `bearer_token` |
| `google_drive` | encrypted `access_token`, optional `folder_id`, `page_size` |

Connector credentials are split from public source config and encrypted in
PostgreSQL. Google Drive permissions are fetched from the upstream Drive
permissions API and propagated to documents, chunks, and vector payloads for
ACL-aware retrieval. Other connectors may still use configured `allowed_users`
and `allowed_groups` as source-level ACL defaults.

## Sync API

```bash
curl -X POST http://localhost:8000/api/v1/sources/{source_id}/sync \
  -H "Authorization: Bearer $TOKEN"
```

The response is an ingestion job. The connector worker records `discovered`, `fetched`, `queued`, `skipped`, `deleted`, and `checkpoint` in `job.stats`.

Deleted upstream records are handled when a connector emits a discovered item with `deleted=true`. The sync service maps the upstream source ID to the stable document ID and marks the document deleted through the ingestion service.
