# Normalization and deduplication

Status: **Phase 4 implemented**. After parse, the same job runs `PARSED → NORMALIZING → NORMALIZED`. Chunking starts in Phase 5.

## Goals

1. Clean text without destroying meaning (no blanket lowercasing).
2. Drop chrome (cookie banners, repeated PDF headers) while keeping policy body.
3. Detect language for later filters.
4. Record **exact** and **near** duplicates. Never delete a related document silently.

## Cleaning

Each parsed block is copied to `normalized_text`:

| Step | Behavior |
| --- | --- |
| Unicode | NFC |
| Entities | `html.unescape` (`&nbsp;`, `&amp;`, …) |
| Line endings | `\n` |
| Whitespace | Collapse in prose; keep newlines in lists/tables; keep indentation in code |
| Empty blocks | Flagged `dropped`, original `text` retained |
| Boilerplate | Short paragraphs matching cookie/nav/copyright patterns |
| Headers/footers | Same first/last line on 2+ pages |

Original `text` stays on the block so the document explorer can show both.

## Language

Stopword density over `en` / `fr` / `de` / `es`. Short or mixed text is `und`. The detector is deterministic (no seeded RNG model).

## Deduplication

Two hashes:

- **Raw SHA-256** (Phase 2): skip reprocessing the *same* document when bytes are unchanged.
- **Normalized SHA-256**: detect the *same cleaned text* under a different filename or source.

Near-duplicates use a 64-bit **SimHash** of word tokens. Hamming distance ≤ `near_duplicate_max_hamming` (default 3) records a `near` relationship.

Fingerprints exclude `title` blocks (often filename stems) so the same body under two names still matches. Headings, paragraphs, lists, code, and tables are included.

Relationships live in `document_duplicates`. The older document is canonical; the newer one gets `canonical_document_id` for exact matches only. Both rows remain `NORMALIZED`.

If two identical bodies are ingested **concurrently**, each job may finish before the other is visible; a later `reprocess` (or a subsequent upload of a third copy) records the relationship. Sequential ingestions always link.

```text
GET /api/v1/documents/{id}/duplicates
```

## How to run

```bash
docker compose exec api alembic upgrade head
docker compose restart api worker

# two filenames, same bytes → two documents + exact duplicate row
curl -F "file=@policy.txt;filename=handbook.txt" http://localhost:8000/api/v1/documents/upload
curl -F "file=@policy.txt;filename=leave-policy.txt" http://localhost:8000/api/v1/documents/upload
```
