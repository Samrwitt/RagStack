"""Application configuration loaded from environment variables.

Settings are the single source of truth for process configuration. Secrets
must come from the environment (or a secrets manager in later phases), never
from source control.
"""

from functools import lru_cache
from typing import Literal

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for API, workers, and supporting clients."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "RagStack"
    app_env: Literal["development", "staging", "production", "test"] = "development"
    debug: bool = False
    secret_key: str = "dev-only-change-me"
    access_token_expire_minutes: int = 60 * 8
    credential_encryption_key: str = ""
    api_v1_prefix: str = "/api/v1"
    cors_origins: str = "http://localhost:3000"
    log_level: str = "INFO"
    log_format: Literal["json", "console"] = "json"

    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "ragstack"
    postgres_password: str = "ragstack"
    postgres_db: str = "ragstack"
    postgres_pool_size: int = 5
    postgres_max_overflow: int = 10

    redis_url: str = "redis://localhost:6379/0"

    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"
    celery_worker_concurrency: int = 2

    s3_endpoint_url: str = "http://localhost:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_bucket: str = "ragstack"
    s3_region: str = "us-east-1"
    s3_secure: bool | None = None

    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""

    max_upload_size_bytes: int = 50 * 1024 * 1024
    allowed_upload_mime_types: str = (
        "text/plain,text/markdown,text/html,application/pdf,"
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    default_organization_id: str = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeee1"
    health_celery_timeout_seconds: float = 3.0
    pdf_ocr_enabled: bool = True
    pdf_ocr_min_chars_per_page: int = 40
    near_duplicate_max_hamming: int = 3
    near_duplicate_scan_limit: int = 500
    chunk_strategy: str = "parent_child"
    chunk_size: int = 256
    chunk_overlap: int = 32
    parent_chunk_max_tokens: int = 1024
    embedding_provider: str = "openai"
    embedding_model: str = "text-embedding-3-small"
    embedding_dimension: int = 1536
    embedding_batch_size: int = 32
    embedding_max_retries: int = 3
    embedding_retry_base_seconds: float = 0.05
    embedding_version: int = 1
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_timeout_seconds: float = 30.0
    llm_model: str = "gpt-4o-mini"
    llm_max_tokens: int = 700
    qdrant_collection: str = "ragstack_chunks"
    reranker_provider: str = "cohere"
    reranker_enabled: bool = True
    reranker_candidate_k: int = 50
    reranker_model: str = "rerank-v3.5"
    reranker_timeout_seconds: float = 30.0
    cohere_api_key: str = ""
    cohere_base_url: str = "https://api.cohere.com"
    context_token_budget: int = 1600
    llm_provider: str = "openai"
    min_grounding_score: float = 0.01
    rate_limit_enabled: bool = True
    rate_limit_requests: int = 120
    rate_limit_window_seconds: int = 60

    @computed_field  # type: ignore[prop-decorator]
    @property
    def credential_key_material(self) -> str:
        return self.credential_encryption_key or self.secret_key

    @computed_field  # type: ignore[prop-decorator]
    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def async_database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def sync_database_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def s3_use_tls(self) -> bool:
        if self.s3_secure is not None:
            return self.s3_secure
        return self.s3_endpoint_url.startswith("https://")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def s3_endpoint_host(self) -> str:
        """MinIO/S3 client wants host:port, not a full URL."""
        endpoint = self.s3_endpoint_url
        for prefix in ("https://", "http://"):
            if endpoint.startswith(prefix):
                endpoint = endpoint[len(prefix) :]
                break
        return endpoint.rstrip("/")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def qdrant_api_key_or_none(self) -> str | None:
        return self.qdrant_api_key or None


@lru_cache
def get_settings() -> Settings:
    return Settings()


def clear_settings_cache() -> None:
    """Test helper so env changes are picked up between cases."""
    get_settings.cache_clear()
