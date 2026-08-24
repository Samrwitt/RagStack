"""Health and readiness endpoints.

GET /health                 process liveness (no dependency I/O)
GET /api/v1/health          detailed component checks
GET /api/v1/health/ready    Kubernetes-style readiness for required deps
"""

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from app import __version__
from app.core.health import HealthReport, collect_health

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthReport)
async def detailed_health(
    celery: bool = Query(default=False, description="Also ping a Celery worker"),
) -> JSONResponse:
    report = await collect_health(include_celery=celery)
    status_code = 200 if report.status != "unhealthy" else 503
    return JSONResponse(status_code=status_code, content=report.model_dump())


@router.get("/health/ready")
async def readiness() -> JSONResponse:
    report = await collect_health(include_celery=False)
    payload = {
        "status": report.status,
        "version": report.version,
        "checks": {item.name: item.status for item in report.checks},
    }
    status_code = 200 if report.status == "ok" else 503
    return JSONResponse(status_code=status_code, content=payload)


def liveness_payload() -> dict[str, str]:
    return {"status": "ok", "service": "corpusforge", "version": __version__}
