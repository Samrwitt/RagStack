"""Dependency-free health probes for control-plane infrastructure.

Readiness requires PostgreSQL, Redis, MinIO, and Qdrant. Celery is reported
on the detailed health endpoint but does not block readiness: the API can
serve traffic while workers are still scaling up.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Literal

from pydantic import BaseModel, Field
from sqlalchemy import text

from app import __version__
from app.core.config import Settings, get_settings
from app.core.db import get_async_engine
from app.core.qdrant import ping_qdrant
from app.core.redis import get_redis
from app.core.storage import ObjectStorage

ComponentStatus = Literal["ok", "error"]
OverallStatus = Literal["ok", "degraded", "unhealthy"]


class ComponentHealth(BaseModel):
    name: str
    status: ComponentStatus
    latency_ms: float
    detail: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class HealthReport(BaseModel):
    status: OverallStatus
    service: str = "corpusforge"
    version: str = __version__
    checks: list[ComponentHealth]


def _latency_ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 2)


def _overall(checks: list[ComponentHealth], required: set[str]) -> OverallStatus:
    required_failed = any(c.name in required and c.status != "ok" for c in checks)
    any_failed = any(c.status != "ok" for c in checks)
    if required_failed:
        return "unhealthy"
    if any_failed:
        return "degraded"
    return "ok"


async def check_postgres(settings: Settings | None = None) -> ComponentHealth:
    started = time.perf_counter()
    try:
        engine = get_async_engine(settings)
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return ComponentHealth(name="postgres", status="ok", latency_ms=_latency_ms(started))
    except Exception as exc:  # noqa: BLE001
        return ComponentHealth(
            name="postgres",
            status="error",
            latency_ms=_latency_ms(started),
            detail=str(exc),
        )


async def check_redis(settings: Settings | None = None) -> ComponentHealth:
    started = time.perf_counter()
    try:
        redis = get_redis(settings)
        pong = await redis.ping()
        if not pong:
            raise RuntimeError("redis ping returned falsy response")
        return ComponentHealth(name="redis", status="ok", latency_ms=_latency_ms(started))
    except Exception as exc:  # noqa: BLE001
        return ComponentHealth(
            name="redis",
            status="error",
            latency_ms=_latency_ms(started),
            detail=str(exc),
        )


async def check_minio(settings: Settings | None = None) -> ComponentHealth:
    started = time.perf_counter()
    cfg = settings or get_settings()

    def _probe() -> None:
        ObjectStorage(cfg).ping()

    try:
        await asyncio.to_thread(_probe)
        return ComponentHealth(
            name="minio",
            status="ok",
            latency_ms=_latency_ms(started),
            metadata={"bucket": cfg.s3_bucket},
        )
    except Exception as exc:  # noqa: BLE001
        return ComponentHealth(
            name="minio",
            status="error",
            latency_ms=_latency_ms(started),
            detail=str(exc),
        )


async def check_qdrant(settings: Settings | None = None) -> ComponentHealth:
    started = time.perf_counter()
    try:
        collection_count = await asyncio.to_thread(ping_qdrant, settings)
        return ComponentHealth(
            name="qdrant",
            status="ok",
            latency_ms=_latency_ms(started),
            metadata={"collections": collection_count},
        )
    except Exception as exc:  # noqa: BLE001
        return ComponentHealth(
            name="qdrant",
            status="error",
            latency_ms=_latency_ms(started),
            detail=str(exc),
        )


async def check_celery(settings: Settings | None = None) -> ComponentHealth:
    """Enqueue a ping task. Optional: worker may still be starting."""
    started = time.perf_counter()
    cfg = settings or get_settings()
    try:
        from app.workers.tasks import ping as ping_task

        async_result = await asyncio.to_thread(ping_task.delay)
        value = await asyncio.to_thread(async_result.get, cfg.health_celery_timeout_seconds)
        if value != "pong":
            raise RuntimeError(f"unexpected ping result: {value!r}")
        return ComponentHealth(name="celery", status="ok", latency_ms=_latency_ms(started))
    except Exception as exc:  # noqa: BLE001
        return ComponentHealth(
            name="celery",
            status="error",
            latency_ms=_latency_ms(started),
            detail=str(exc),
        )


REQUIRED_READINESS = {"postgres", "redis", "minio", "qdrant"}


async def collect_health(*, include_celery: bool = False) -> HealthReport:
    settings = get_settings()
    probes = [
        check_postgres(settings),
        check_redis(settings),
        check_minio(settings),
        check_qdrant(settings),
    ]
    if include_celery:
        probes.append(check_celery(settings))
    checks = list(await asyncio.gather(*probes))
    return HealthReport(status=_overall(checks, REQUIRED_READINESS), checks=checks)
