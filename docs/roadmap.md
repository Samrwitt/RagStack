# Roadmap

Status through Phase 5: foundation, ingestion, parsing, normalization, deduplication, and chunking are implemented. The remaining work turns those chunks into a searchable, permission-aware, evaluable RAG product.

## Phase 6 - Embeddings & Vector Index

Status: **in progress**. The first slice includes the provider abstraction, deterministic dev provider, batching/retries, Qdrant collection management, vector payload metadata, embedding records, and Celery task wiring.

Goal: convert finalized chunks into versioned vectors and persist them in Qdrant with enough payload metadata for retrieval, filtering, deletion, and re-embedding.

Deliverables:

- Embedding provider abstraction with model name, vector size, batch limits, timeout, and retry policy.
- Local/dev embedding provider for deterministic tests.
- Batch embedding service that accepts chunk IDs and writes embedding attempts/results.
- Qdrant collection manager for collection creation, schema validation, payload indexes, and vector-size mismatch detection.
- Chunk vector metadata: organization, workspace, source, document, document version, chunk ID, ACL principals, URL, title, page, section, language, hash, parser/chunker/embedder versions.
- Idempotent vector upserts keyed by chunk/version/embedder.
- Re-embedding workflow for provider/model changes and stale vector detection.
- Deletion/tombstone handling when documents or versions are superseded.

Acceptance checks:

- Re-running embedding jobs does not create duplicate vector points.
- Only current document versions are indexed as searchable.
- Collection startup fails clearly if the configured embedding dimension does not match Qdrant.
- A re-embed run can coexist with the old index until cutover.

Suggested tests:

- Unit tests for provider retries, batching, idempotency keys, and stale-vector detection.
- Integration tests for Qdrant collection creation, payload indexes, upsert, delete, and search smoke checks.

## Phase 7 - Search

Status: **complete**. Includes retrieval contracts, dense Qdrant retrieval, BM25 over current chunks, metadata filters, ACL filtering, Reciprocal Rank Fusion, and a search endpoint.

Goal: provide dense, lexical, and hybrid retrieval with metadata and ACL filters enforced before ranking results are exposed.

Deliverables:

- Dense retrieval against Qdrant.
- BM25 lexical index and query path.
- Hybrid search using dense + BM25 result fusion.
- Reciprocal Rank Fusion with configurable `k`, source weights, and top-k.
- Metadata filters for organization, workspace, source, document type, language, date/version, tags, URL/domain, and arbitrary connector metadata.
- ACL filter compiler that converts caller permissions into Qdrant/BM25 filters.
- Search API returning ranked chunks with scores, provenance, and filter debug data.

Acceptance checks:

- Cross-organization and unauthorized-document leakage is impossible from the search layer.
- Dense-only, sparse-only, and hybrid modes are all available for eval baselines.
- Metadata filters apply consistently across dense and BM25 paths.

Suggested tests:

- Unit tests for RRF, filter compilation, ACL enforcement, and score normalization.
- Integration tests with seeded tenants proving authorized and unauthorized users get different result sets.

## Phase 8 - Reranking

Status: **complete**. Includes a reranker provider boundary, deterministic local reranker, candidate-set reranking, score preservation, request-level enablement, and token-budgeted context selection.

Goal: rerank retrieved candidates before context construction while preserving provenance and exposing scores for debugging/evaluation.

Deliverables:

- Reranker provider abstraction with no-op/dev provider.
- Candidate-size configuration per query mode.
- Score model capturing original rank, dense score, BM25 score, RRF score, reranker score, and final rank.
- Timeout/fallback behavior when reranking is unavailable.
- Context selection strategy that selects final chunks under a token budget and avoids redundant sibling chunks where appropriate.

Acceptance checks:

- Reranking can be enabled/disabled per request or experiment.
- Search still returns useful results when the reranker times out.
- Retrieval debugger can show before/after ranks and score components.

Suggested tests:

- Unit tests for reranker provider interface, fallback path, candidate truncation, and context selection.
- Integration smoke test for hybrid search with reranking enabled.

## Phase 9 - RAG Generation

Status: **complete**. Includes an LLM provider boundary, deterministic grounded extractive provider, citation resolution, insufficient-evidence handling, conversation-aware retrieval query construction, context selection integration, and a chat endpoint.

Goal: answer from retrieved context with citations, clear insufficient-evidence behavior, and conversation-aware retrieval.

Deliverables:

- LLM provider abstraction with chat/completion interface, timeout, retries, and model metadata.
- Grounded answer prompt contract that forbids unsupported claims.
- Citation resolver mapping selected chunks to document title, source, URL, page, section, and connector-specific entity IDs.
- Insufficient-evidence response type.
- Conversation-aware retrieval query generation that uses chat history without leaking it into filters or citations.
- Answer API returning answer text, citations, selected context, retrieval trace ID, and evidence status.

Acceptance checks:

- Every factual claim in a normal answer can be traced to at least one selected citation.
- When retrieval evidence is weak or empty, the response says it cannot find enough information.
- Conversation history can improve retrieval, but ACL and metadata filters remain deterministic.

Suggested tests:

- Unit tests for citation resolution, insufficient-evidence thresholding, prompt input shaping, and response parsing.
- Integration tests with conflicting document versions proving answers cite the current version.

## Phase 10 - Connectors

Status: **complete**. Includes website, GitHub, PostgreSQL, REST API, and Google Drive connector implementations; connector registry; source sync jobs; checkpoint propagation; metadata/ACL normalization; changed-content enqueueing; and deleted-record handling.

Goal: expand collection beyond local upload while preserving the same ingestion, versioning, and replay contracts.

Deliverables:

- Website crawler with robots/rate-limit policy, sitemap support, canonical URL handling, and incremental recrawl.
- GitHub connector for repositories, issues, PRs, discussions, and markdown/docs files.
- PostgreSQL connector for configured tables/views with primary-key checkpoints.
- REST API connector with pagination, auth configuration, cursor checkpoints, and response mapping.
- Google Drive connector for folders/files beyond local upload.
- Connector checkpoint model and sync job API.
- Connector-specific metadata normalized into source/document/chunk payloads.

Acceptance checks:

- Each connector emits canonical document identities and stable content hashes.
- Failed syncs can resume from checkpoints without duplicating documents.
- Connector secrets are never logged or stored in plaintext.

Suggested tests:

- Contract tests for connector protocols.
- Mocked integration tests for pagination, checkpointing, changed/deleted records, and rate-limit handling.

## Phase 11 - Evaluation

Goal: make retrieval and answer quality measurable and comparable across configurations.

Deliverables:

- Evaluation dataset schema and seed/demo dataset.
- Retrieval metrics: Recall@K, Precision@K, MRR, and nDCG.
- Answer metrics: groundedness, answer relevance, citation correctness, and citation completeness.
- Experiment configuration for chunking, retrieval mode, top-k, reranker, context budget, and model/provider.
- Evaluation run API and persisted run results.
- Experiment comparison table and export format.

Acceptance checks:

- A run records the exact configuration and code/model versions needed to reproduce it.
- Retrieval metrics can run without generation providers.
- Answer metrics distinguish missing citations from unsupported claims.

Suggested tests:

- Unit tests for metric formulas and edge cases.
- Integration tests for a small seeded corpus with known relevant documents.

## Phase 12 - Frontend

Goal: provide a Next.js dashboard for operating, debugging, and evaluating the platform.

Deliverables:

- Overview page with health, active jobs, indexed document counts, ingestion failures, and query latency.
- Sources page for connector configuration, sync status, and manual sync.
- Documents page for document versions, chunks, parse metadata, and deletion/reprocessing actions.
- Chat page with grounded answers and citations.
- Retrieval Debugger showing original query, rewritten query, filters, dense hits, BM25 hits, RRF results, reranker scores, and final context.
- Evaluation page for datasets, runs, metric tables, and experiment comparison.
- Jobs page for queue status, retries, failures, and task detail.
- Settings page for providers, models, retrieval defaults, rate limits, roles, and ACL policy.

Acceptance checks:

- The first screen is the actual dashboard, not a marketing page.
- Debug views expose enough trace detail to explain why a query returned its answer.
- Error and empty states are clear for users operating a real system.

Suggested tests:

- Component tests for core tables/forms.
- End-to-end tests for source creation, document inspection, chat with citations, and retrieval debugging.

## Phase 13 - Production Hardening

Goal: make the system safer to operate with stronger failure handling, observability, authorization, and abuse controls.

Deliverables:

- Dead-letter queue handling and replay UI/API.
- Richer retry policies with per-task backoff, poison-message detection, and retry budgets.
- Queue monitoring, worker heartbeats, and stuck-job detection.
- Metrics for ingestion, parsing, embedding, indexing, retrieval, reranking, generation, and evaluation.
- JWT/session authentication.
- RBAC for organizations/workspaces/sources/documents/settings.
- ACL enforcement tests at API, retrieval, and vector-index layers.
- Rate limiting for ingestion, sync, search, generation, and connector calls.
- Security tests for tenant isolation, secret handling, SSRF in crawlers/connectors, and prompt-injection-resistant citation behavior.

Acceptance checks:

- Unauthorized users cannot discover document existence through search, citations, jobs, or errors.
- Operators can inspect and replay failed jobs without manual database edits.
- Rate limits fail closed and return actionable API errors.

Suggested tests:

- Unit and integration tests for RBAC policies and ACL filters.
- Security-focused regression tests for cross-tenant access, connector URL validation, and secret redaction.

## Recommended Build Order

1. Phase 6: embeddings and Qdrant indexing, because search depends on stable vector payloads.
2. Phase 7: retrieval API with dense first, then BM25, then hybrid/RRF and ACL filters.
3. Phase 8: reranking and context selection.
4. Phase 9: grounded generation and citations.
5. Phase 11: evaluation harness once retrieval/generation contracts exist.
6. Phase 10: additional connectors after the core pipeline is measurable.
7. Phase 12: frontend once the backend APIs are stable enough to operate.
8. Phase 13: hardening throughout, with final dedicated passes before considering the platform production-ready.

Phase 13 should not wait entirely until the end for ACL and tenant-isolation tests. Those belong in Phase 7 as soon as retrieval exists, then become stricter in the hardening phase.
