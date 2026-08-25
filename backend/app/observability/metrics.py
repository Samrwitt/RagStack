"""Prometheus and OpenTelemetry metrics registry."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from threading import Lock
from typing import Any

try:
    import prometheus_client
    from prometheus_client import CollectorRegistry, Counter, Gauge, Summary, generate_latest, REGISTRY
    HAS_PROMETHEUS = True
except ImportError:  # pragma: no cover
    HAS_PROMETHEUS = False
    REGISTRY = None  # type: ignore[assignment]

try:
    from opentelemetry import metrics as otel_metrics
    _otel_meter = otel_metrics.get_meter("corpusforge")
    HAS_OTEL = True
except ImportError:  # pragma: no cover
    HAS_OTEL = False
    _otel_meter = None

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

_prom_counters: dict[str, Any] = {}
_prom_gauges: dict[str, Any] = {}
_prom_summaries: dict[str, Any] = {}
_otel_counters: dict[str, Any] = {}
_otel_histograms: dict[str, Any] = {}


def increment(
    name: str,
    amount: float = 1.0,
    *,
    labels: Mapping[str, object] | None = None,
) -> None:
    lbl_dict = {str(k): str(v) for k, v in (labels or {}).items()}
    with _lock:
        _counters[_key(name, labels)] += amount

        if HAS_PROMETHEUS:
            try:
                if name not in _prom_counters:
                    _prom_counters[name] = Counter(
                        name, f"Metric {name}", labelnames=list(lbl_dict.keys())
                    )
                counter_obj = _prom_counters[name]
                if lbl_dict:
                    counter_obj.labels(**lbl_dict).inc(amount)
                else:
                    counter_obj.inc(amount)
            except Exception:  # pragma: no cover
                pass

        if HAS_OTEL and _otel_meter is not None:
            try:
                if name not in _otel_counters:
                    _otel_counters[name] = _otel_meter.create_counter(name)
                _otel_counters[name].add(amount, attributes=lbl_dict)
            except Exception:  # pragma: no cover
                pass


def set_gauge(
    name: str,
    value: float,
    *,
    labels: Mapping[str, object] | None = None,
) -> None:
    lbl_dict = {str(k): str(v) for k, v in (labels or {}).items()}
    with _lock:
        _gauges[_key(name, labels)] = value

        if HAS_PROMETHEUS:
            try:
                if name not in _prom_gauges:
                    _prom_gauges[name] = Gauge(
                        name, f"Metric {name}", labelnames=list(lbl_dict.keys())
                    )
                gauge_obj = _prom_gauges[name]
                if lbl_dict:
                    gauge_obj.labels(**lbl_dict).set(value)
                else:
                    gauge_obj.set(value)
            except Exception:  # pragma: no cover
                pass


def observe(
    name: str,
    value: float,
    *,
    labels: Mapping[str, object] | None = None,
) -> None:
    lbl_dict = {str(k): str(v) for k, v in (labels or {}).items()}
    with _lock:
        bucket = _observations[_key(name, labels)]
        bucket["count"] += 1
        bucket["sum"] += value

        if HAS_PROMETHEUS:
            try:
                if name not in _prom_summaries:
                    _prom_summaries[name] = Summary(
                        name, f"Metric {name}", labelnames=list(lbl_dict.keys())
                    )
                summary_obj = _prom_summaries[name]
                if lbl_dict:
                    summary_obj.labels(**lbl_dict).observe(value)
                else:
                    summary_obj.observe(value)
            except Exception:  # pragma: no cover
                pass

        if HAS_OTEL and _otel_meter is not None:
            try:
                if name not in _otel_histograms:
                    _otel_histograms[name] = _otel_meter.create_histogram(name)
                _otel_histograms[name].record(value, attributes=lbl_dict)
            except Exception:  # pragma: no cover
                pass


def render_prometheus(metrics: dict[str, float] | None = None) -> str:
    if metrics is not None:
        return "\n".join(f"{name} {value}" for name, value in sorted(metrics.items())) + "\n"

    if HAS_PROMETHEUS and REGISTRY is not None:
        try:
            prom_output = generate_latest(REGISTRY).decode("utf-8")
            if prom_output.strip():
                return prom_output
        except Exception:  # pragma: no cover
            pass

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
