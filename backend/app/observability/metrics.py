"""Small Prometheus-compatible metrics registry."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from threading import Lock

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


_MetricKey = tuple[str, tuple[tuple[str, str], ...]]

_lock = Lock()
_counters: defaultdict[_MetricKey, float] = defaultdict(float)
_gauges: dict[_MetricKey, float] = {}
_observations: defaultdict[_MetricKey, dict[str, float]] = defaultdict(
    lambda: {"count": 0.0, "sum": 0.0}
)


def increment(
    name: str,
    amount: float = 1.0,
    *,
    labels: Mapping[str, object] | None = None,
) -> None:
    with _lock:
        _counters[_key(name, labels)] += amount


def set_gauge(
    name: str,
    value: float,
    *,
    labels: Mapping[str, object] | None = None,
) -> None:
    with _lock:
        _gauges[_key(name, labels)] = value


def observe(
    name: str,
    value: float,
    *,
    labels: Mapping[str, object] | None = None,
) -> None:
    with _lock:
        bucket = _observations[_key(name, labels)]
        bucket["count"] += 1
        bucket["sum"] += value


def render_prometheus(metrics: dict[str, float] | None = None) -> str:
    if metrics is not None:
        return "\n".join(f"{name} {value}" for name, value in sorted(metrics.items())) + "\n"
    lines: list[str] = []
    with _lock:
        counters = dict(_counters)
        gauges = dict(_gauges)
        observations = {key: dict(value) for key, value in _observations.items()}
    typed: set[str] = set()
    for (name, labels), value in sorted(counters.items()):
        _append_type(lines, typed, name, "counter")
        lines.append(f"{name}{_labels(labels)} {_format_value(value)}")
    for (name, labels), value in sorted(gauges.items()):
        _append_type(lines, typed, name, "gauge")
        lines.append(f"{name}{_labels(labels)} {_format_value(value)}")
    for (name, labels), value in sorted(observations.items()):
        _append_type(lines, typed, name, "summary")
        label_text = _labels(labels)
        lines.append(f"{name}_count{label_text} {_format_value(value['count'])}")
        lines.append(f"{name}_sum{label_text} {_format_value(value['sum'])}")
    return "\n".join(lines) + ("\n" if lines else "")


def _key(name: str, labels: Mapping[str, object] | None = None) -> _MetricKey:
    return (
        name,
        tuple(sorted((str(key), str(value)) for key, value in (labels or {}).items())),
    )


def _labels(labels: tuple[tuple[str, str], ...]) -> str:
    if not labels:
        return ""
    values = ",".join(f'{key}="{_escape_label(value)}"' for key, value in labels)
    return "{" + values + "}"


def _escape_label(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def _append_type(lines: list[str], typed: set[str], name: str, metric_type: str) -> None:
    if name in typed:
        return
    lines.append(f"# TYPE {name} {metric_type}")
    typed.add(name)


def _format_value(value: float) -> str:
    number = float(value)
    if number.is_integer():
        return str(int(number))
    return repr(number)
