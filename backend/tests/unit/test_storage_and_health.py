from app.core.health import ComponentHealth, _overall
from app.core.storage import parse_s3_endpoint, raw_object_key


def test_raw_object_key_layout() -> None:
    key = raw_object_key(
        source="github",
        document_id="doc-42",
        version=3,
        filename="original.md",
    )
    assert key == "raw/github/doc-42/v3/original.md"


def test_raw_object_key_strips_path_traversal() -> None:
    key = raw_object_key(
        source="../github",
        document_id="abc/../def",
        version=1,
        filename="../original.pdf",
    )
    assert ".." not in key
    assert key.startswith("raw/")


def test_parse_s3_endpoint_http() -> None:
    host, secure = parse_s3_endpoint("http://minio:9000")
    assert host == "minio:9000"
    assert secure is False


def test_parse_s3_endpoint_https() -> None:
    host, secure = parse_s3_endpoint("https://s3.amazonaws.com")
    assert host == "s3.amazonaws.com"
    assert secure is True


def test_overall_health_unhealthy_if_required_fails() -> None:
    checks = [
        ComponentHealth(name="postgres", status="error", latency_ms=1),
        ComponentHealth(name="celery", status="ok", latency_ms=1),
    ]
    assert _overall(checks, {"postgres"}) == "unhealthy"


def test_overall_health_degraded_if_optional_fails() -> None:
    checks = [
        ComponentHealth(name="postgres", status="ok", latency_ms=1),
        ComponentHealth(name="celery", status="error", latency_ms=1),
    ]
    assert _overall(checks, {"postgres"}) == "degraded"
