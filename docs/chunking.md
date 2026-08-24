# Chunking

Status: **Phase 5 implemented**. After normalize, the same job runs `NORMALIZED → CHUNKING → CHUNKED`. Embedding starts in Phase 6.

## Goals

1. Turn cleaned blocks into retrieval units without losing section/page context.
2. Offer multiple strategies with the same storage contract.
3. Support parent/child hierarchy for section-level context + precise retrieval.

## Strategies

| Name | Behavior |
| --- | --- |
| `fixed` | Sliding window over whitespace tokens (`chunk_size`, `chunk_overlap`) |
| `recursive` | Split by paragraphs → lines → sentences → tokens, then pack to size |
| `heading_aware` | Group under headings; keep tables/code atomic when possible |
| `parent_child` (**default**) | One parent per section + child retrieval chunks linked by `parent_chunk_id` |

Config (env):

```text
CHUNK_STRATEGY=parent_child
CHUNK_SIZE=256
CHUNK_OVERLAP=32
PARENT_CHUNK_MAX_TOKENS=1024
```

Token counts use deterministic whitespace tokens (not a model tokenizer). That keeps tests and fingerprints stable until Phase 6 picks an embedding tokenizer.

## Storage

`document_chunks`:

```text
chunk_id, document_id, version_id, parent_chunk_id,
ordinal, text, token_count, page, section,
strategy, kind (parent|child|leaf), metadata
```

Version metadata: `chunk_strategy`, `chunker_version`, `chunk_count`, `chunked_at`.

Dropped boilerplate blocks are ignored. Original block text remains on `document_blocks`.

## API

```text
GET /api/v1/documents/{id}/chunks
GET /api/v1/documents/{id}/chunks?version=1
```

## How to run

```bash
docker compose exec api alembic upgrade head
docker compose restart api worker

curl -F "file=@handbook.md;filename=handbook.md;type=text/markdown" \
  http://localhost:8000/api/v1/documents/upload
# wait until current_state is CHUNKED
curl -s http://localhost:8000/api/v1/documents/{id}/chunks
```
