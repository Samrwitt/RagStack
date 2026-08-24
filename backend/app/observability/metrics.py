"""Reserved metric names for ingestion, retrieval, and generation.

Counters and histograms are wired in Phase 13. Declaring names early keeps
later instrumentation consistent.
"""

INGEST_DOCUMENTS_DISCOVERED = "corpusforge_ingest_documents_discovered_total"
INGEST_DOCUMENTS_PROCESSED = "corpusforge_ingest_documents_processed_total"
INGEST_DOCUMENTS_FAILED = "corpusforge_ingest_documents_failed_total"
INGEST_DOCUMENTS_SKIPPED = "corpusforge_ingest_documents_skipped_total"
INGEST_QUEUE_DEPTH = "corpusforge_ingest_queue_depth"
INGEST_PROCESSING_LATENCY_SECONDS = "corpusforge_ingest_processing_latency_seconds"

RETRIEVAL_LATENCY_SECONDS = "corpusforge_retrieval_latency_seconds"
RERANK_LATENCY_SECONDS = "corpusforge_rerank_latency_seconds"
RETRIEVAL_ZERO_RESULTS = "corpusforge_retrieval_zero_results_total"

GENERATION_LATENCY_SECONDS = "corpusforge_generation_latency_seconds"
GENERATION_INPUT_TOKENS = "corpusforge_generation_input_tokens_total"
GENERATION_OUTPUT_TOKENS = "corpusforge_generation_output_tokens_total"
GENERATION_FAILURES = "corpusforge_generation_failures_total"
RATE_LIMIT_REJECTIONS = "corpusforge_rate_limit_rejections_total"
DLQ_JOBS = "corpusforge_dlq_jobs_total"


def render_prometheus(metrics: dict[str, float]) -> str:
    return "\n".join(f"{name} {value}" for name, value in sorted(metrics.items())) + "\n"
