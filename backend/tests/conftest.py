"""Pytest configuration shared by unit and integration tests."""

import os

import pytest

os.environ.setdefault("APP_ENV", "test")
os.environ["DEBUG"] = "false"
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("POSTGRES_HOST", "localhost")
os.environ.setdefault("POSTGRES_PORT", "5433")
os.environ.setdefault("POSTGRES_USER", "corpusforge")
os.environ.setdefault("POSTGRES_PASSWORD", "corpusforge")
os.environ.setdefault("POSTGRES_DB", "corpusforge")
os.environ.setdefault("REDIS_URL", "redis://localhost:6380/0")
os.environ.setdefault("CELERY_BROKER_URL", "redis://localhost:6380/1")
os.environ.setdefault("CELERY_RESULT_BACKEND", "redis://localhost:6380/2")
os.environ.setdefault("S3_ENDPOINT_URL", "http://localhost:9000")
os.environ.setdefault("S3_ACCESS_KEY", "minioadmin")
os.environ.setdefault("S3_SECRET_KEY", "minioadmin")
os.environ.setdefault("S3_BUCKET", "corpusforge")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")
os.environ.setdefault("LOG_FORMAT", "console")
os.environ.setdefault("LOG_LEVEL", "WARNING")
os.environ.setdefault("EMBEDDING_PROVIDER", "deterministic")
os.environ.setdefault("EMBEDDING_MODEL", "deterministic-v1")
os.environ.setdefault("EMBEDDING_DIMENSION", "128")
os.environ.setdefault("LLM_PROVIDER", "extractive")
os.environ.setdefault("RERANKER_PROVIDER", "lexical_overlap")
os.environ.setdefault("RERANKER_ENABLED", "true")

from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import clear_settings_cache  # noqa: E402
from app.main import create_app  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_settings_cache() -> None:
    clear_settings_cache()
    yield
    clear_settings_cache()


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
def client(app):
    with TestClient(app) as test_client:
        yield test_client
