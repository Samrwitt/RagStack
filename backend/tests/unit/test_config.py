import pytest

from app.core.config import Settings, clear_settings_cache, get_settings


def test_cors_origin_list_splits_and_strips() -> None:
    settings = Settings(cors_origins="http://localhost:3000, https://app.example.com")
    assert settings.cors_origin_list == [
        "http://localhost:3000",
        "https://app.example.com",
    ]


def test_database_urls_use_expected_drivers() -> None:
    settings = Settings(
        postgres_host="db.internal",
        postgres_port=5433,
        postgres_user="cf",
        postgres_password="secret",
        postgres_db="corpusforge",
    )
    assert settings.async_database_url.startswith("postgresql+asyncpg://")
    assert settings.sync_database_url.startswith("postgresql+psycopg://")
    assert "db.internal:5433/corpusforge" in settings.async_database_url
    assert "db.internal:5433/corpusforge" in settings.sync_database_url


def test_s3_endpoint_host_strips_scheme() -> None:
    settings = Settings(s3_endpoint_url="http://minio:9000")
    assert settings.s3_endpoint_host == "minio:9000"
    assert settings.s3_use_tls is False


def test_s3_https_enables_tls() -> None:
    settings = Settings(s3_endpoint_url="https://s3.amazonaws.com")
    assert settings.s3_use_tls is True


def test_qdrant_empty_api_key_becomes_none() -> None:
    settings = Settings(qdrant_api_key="")
    assert settings.qdrant_api_key_or_none is None


def test_settings_cache_can_be_cleared(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_NAME", "cached-a")
    clear_settings_cache()
    assert get_settings().app_name == "cached-a"
    monkeypatch.setenv("APP_NAME", "cached-b")
    assert get_settings().app_name == "cached-a"
    clear_settings_cache()
    assert get_settings().app_name == "cached-b"
