"""Security helpers for connectors and logs."""

from __future__ import annotations

import ipaddress
from urllib.parse import urlparse

SECRET_KEYS = {"token", "access_token", "bearer_token", "password", "secret", "api_key"}


def redact_secrets(payload: dict) -> dict:
    redacted = {}
    for key, value in payload.items():
        if key.lower() in SECRET_KEYS:
            redacted[key] = "***REDACTED***"
        elif isinstance(value, dict):
            redacted[key] = redact_secrets(value)
        else:
            redacted[key] = value
    return redacted


def validate_public_http_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("URL must be http(s)")
    host = parsed.hostname
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return
    if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
        raise ValueError("URL points to a non-public IP address")
