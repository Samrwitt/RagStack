from datetime import timedelta

import pytest

from app.auth.rbac import Permission, can
from app.core.rate_limit import FixedWindowRateLimiter
from app.core.security import (
    create_access_token,
    decode_access_token,
    decrypt_json,
    encrypt_json,
    hash_password,
    redact_secrets,
    split_sensitive_config,
    validate_public_http_url,
    verify_password,
)
from app.models.enums import Role
from app.observability.metrics import render_prometheus


def test_rbac_permissions() -> None:
    assert can(Role.OWNER, Permission.SETTINGS)
    assert can(Role.EDITOR, Permission.WRITE)
    assert not can(Role.VIEWER, Permission.WRITE)


def test_secret_redaction_is_recursive() -> None:
    assert redact_secrets({"token": "abc", "nested": {"api_key": "123"}, "name": "ok"}) == {
        "token": "***REDACTED***",
        "nested": {"api_key": "***REDACTED***"},
        "name": "ok",
    }


def test_password_hash_and_verify() -> None:
    stored = hash_password("correct")

    assert verify_password("correct", stored)
    assert not verify_password("wrong", stored)


def test_access_token_round_trip() -> None:
    token = create_access_token(
        subject="user-id",
        organization_id="org-id",
        secret_key="secret",
        expires_delta=timedelta(minutes=5),
    )

    claims = decode_access_token(token, secret_key="secret")

    assert claims["sub"] == "user-id"
    assert claims["org"] == "org-id"


def test_connector_credentials_are_encrypted_and_split() -> None:
    public, secrets = split_sensitive_config(
        {"base_url": "https://example.test", "access_token": "secret-token"}
    )
    encrypted = encrypt_json(secrets, key_material="key")

    assert public == {"base_url": "https://example.test"}
    assert "secret-token" not in encrypted
    assert decrypt_json(encrypted, key_material="key") == {"access_token": "secret-token"}


def test_validate_public_http_url_rejects_private_ip() -> None:
    with pytest.raises(ValueError):
        validate_public_http_url("http://127.0.0.1/admin")
    validate_public_http_url("https://example.com/docs")


def test_fixed_window_rate_limiter() -> None:
    limiter = FixedWindowRateLimiter(limit=2, window_seconds=60)

    assert limiter.allow("org")[0] is True
    assert limiter.allow("org")[0] is True
    assert limiter.allow("org")[0] is False


def test_prometheus_rendering() -> None:
    assert render_prometheus({"z": 2, "a": 1}) == "a 1\nz 2\n"
