import pytest

from app.auth.rbac import Permission, can
from app.core.rate_limit import FixedWindowRateLimiter
from app.core.security import redact_secrets, validate_public_http_url
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
