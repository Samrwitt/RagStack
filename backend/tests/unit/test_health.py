from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app import __version__
from app.core.health import ComponentHealth, HealthReport


def test_liveness_does_not_touch_dependencies(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "corpusforge"
    assert body["version"] == __version__


def test_liveness_echoes_request_id(client: TestClient) -> None:
    response = client.get("/health", headers={"X-Request-ID": "req-123"})
    assert response.headers["X-Request-ID"] == "req-123"


def test_detailed_health_ok(client: TestClient) -> None:
    report = HealthReport(
        status="ok",
        checks=[
            ComponentHealth(name="postgres", status="ok", latency_ms=1.0),
            ComponentHealth(name="redis", status="ok", latency_ms=1.0),
            ComponentHealth(name="minio", status="ok", latency_ms=1.0),
            ComponentHealth(name="qdrant", status="ok", latency_ms=1.0),
        ],
    )
    with patch("app.api.v1.health.collect_health", new=AsyncMock(return_value=report)):
        response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_readiness_returns_503_when_required_dep_fails(client: TestClient) -> None:
    report = HealthReport(
        status="unhealthy",
        checks=[
            ComponentHealth(name="postgres", status="error", latency_ms=1.0, detail="down"),
            ComponentHealth(name="redis", status="ok", latency_ms=1.0),
            ComponentHealth(name="minio", status="ok", latency_ms=1.0),
            ComponentHealth(name="qdrant", status="ok", latency_ms=1.0),
        ],
    )
    with patch("app.api.v1.health.collect_health", new=AsyncMock(return_value=report)):
        response = client.get("/api/v1/health/ready")
    assert response.status_code == 503
    assert response.json()["status"] == "unhealthy"
    assert response.json()["checks"]["postgres"] == "error"
