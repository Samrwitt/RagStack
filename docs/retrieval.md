# Retrieval

Status: **designed**. Indexing lands in Phase 6; search, hybrid fusion, and ACL filters in Phase 7; reranking in Phase 8; generation in Phase 9.

## Modes

| Mode | Use |
| --- | --- |
| `DENSE` | Semantic similarity via Qdrant using the configured embedding provider |
| `SPARSE` | PostgreSQL full-text search over a persisted `tsvector` GIN index |
| `HYBRID` | Both, fused with Reciprocal Rank Fusion |

Hybrid is the default for production queries. Dense-only is retained for evaluation baselines.

## Query path

```text
user question
  → conversation-aware retrieval query (distinct from chat history)
  → optional rewrite / acronym expansion / multi-query
  → dense + indexed sparse search with metadata + ACL filters
  → RRF
  → rerank (top 50 → top 8)
  → context builder (token budget, provenance)
  → grounded generation + citations
```

The retrieval debugger (Phase 12) exposes every stage: original query, rewritten query, dense hits, sparse hits, RRF order, reranker scores, final context.

## Providers

Production defaults are OpenAI-compatible embeddings and chat generation plus
Cohere reranking:

| Setting | Default |
| --- | --- |
| `EMBEDDING_PROVIDER` | `openai` |
| `EMBEDDING_MODEL` | `text-embedding-3-small` |
| `LLM_PROVIDER` | `openai` |
| `LLM_MODEL` | `gpt-4o-mini` |
| `RERANKER_PROVIDER` | `cohere` |
| `RERANKER_MODEL` | `rerank-v3.5` |

The deterministic embedding provider, lexical-overlap reranker, and extractive
LLM provider remain available for tests and offline fallback configuration.

## Authorization

ACL fields propagate source → document → chunk → Qdrant payload. Filters are applied **in the search request**. Cross-organization leakage is a P0 defect, not a prompt issue.

## Citations

Generated answers must resolve to document title, source type, URL, page, section, and (where relevant) GitHub issue or database entity. Insufficient evidence is a first-class response:

> I could not find enough information in the connected sources.

## Version-aware index

Only the current document version is searchable. Historical versions remain in PostgreSQL and object storage for audit and replay.
