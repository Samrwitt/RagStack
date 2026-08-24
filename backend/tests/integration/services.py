"""Helpers for optional integration tests against docker compose services."""

from __future__ import annotations

import socket
from urllib.parse import urlparse

import pytest

from app.core.config import get_settings


def can_connect(host: str, port: int, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


_settings = get_settings()
_redis = urlparse(_settings.redis_url)
_s3 = urlparse(_settings.s3_endpoint_url)
_qdrant = urlparse(_settings.qdrant_url)

requires_postgres = pytest.mark.skipif(
    not can_connect(_settings.postgres_host, _settings.postgres_port),
    reason=f"PostgreSQL is not running on {_settings.postgres_host}:{_settings.postgres_port}",
)
requires_redis = pytest.mark.skipif(
    not can_connect(_redis.hostname or "127.0.0.1", _redis.port or 6379),
    reason=f"Redis is not running on {_redis.hostname}:{_redis.port}",
)
requires_minio = pytest.mark.skipif(
    not can_connect(_s3.hostname or "127.0.0.1", _s3.port or 9000),
    reason=f"MinIO is not running on {_s3.hostname}:{_s3.port}",
)
requires_qdrant = pytest.mark.skipif(
    not can_connect(_qdrant.hostname or "127.0.0.1", _qdrant.port or 6333),
    reason=f"Qdrant is not running on {_qdrant.hostname}:{_qdrant.port}",
)
