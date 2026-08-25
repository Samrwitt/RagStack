"""Security helpers for connectors and logs."""

from __future__ import annotations

import base64
import hashlib
import hmac
import ipaddress
import json
import os
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlparse

from cryptography.fernet import Fernet, InvalidToken

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


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 210_000)
    return "pbkdf2_sha256$210000$" + _b64(salt) + "$" + _b64(digest)


def verify_password(password: str, stored_hash: str | None) -> bool:
    if not stored_hash:
        return False
    try:
        algorithm, iterations, salt, expected = stored_hash.split("$", 3)
    except ValueError:
        return False
    if algorithm != "pbkdf2_sha256":
        return False
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        _b64decode(salt),
        int(iterations),
    )
    return hmac.compare_digest(_b64(digest), expected)


def create_access_token(
    *,
    subject: str,
    organization_id: str,
    secret_key: str,
    expires_delta: timedelta,
) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": subject,
        "org": organization_id,
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
    }
    signing_input = (
        _b64url_json({"alg": "HS256", "typ": "JWT"})
        + "."
        + _b64url_json(payload)
    )
    signature = hmac.new(
        secret_key.encode("utf-8"),
        signing_input.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return signing_input + "." + _b64url(signature)


def decode_access_token(token: str, *, secret_key: str) -> dict[str, Any]:
    try:
        header_segment, payload_segment, signature_segment = token.split(".", 2)
    except ValueError as exc:
        raise ValueError("invalid token") from exc
    signing_input = f"{header_segment}.{payload_segment}"
    expected = hmac.new(
        secret_key.encode("utf-8"),
        signing_input.encode("ascii"),
        hashlib.sha256,
    ).digest()
    if not hmac.compare_digest(_b64url(expected), signature_segment):
        raise ValueError("invalid token signature")
    payload = json.loads(_b64url_decode(payload_segment))
    if int(payload.get("exp", 0)) < int(datetime.now(UTC).timestamp()):
        raise ValueError("token expired")
    return payload


def encrypt_json(payload: dict[str, Any], *, key_material: str) -> str:
    return _fernet(key_material).encrypt(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    ).decode("ascii")


def decrypt_json(token: str | None, *, key_material: str) -> dict[str, Any]:
    if not token:
        return {}
    try:
        data = _fernet(key_material).decrypt(token.encode("ascii"))
    except InvalidToken as exc:
        raise ValueError("could not decrypt connector credentials") from exc
    return json.loads(data.decode("utf-8"))


def split_sensitive_config(config: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    public: dict[str, Any] = {}
    secrets: dict[str, Any] = {}
    for key, value in config.items():
        if key.lower() in SECRET_KEYS:
            secrets[key] = value
        elif isinstance(value, dict):
            nested_public, nested_secrets = split_sensitive_config(value)
            public[key] = nested_public
            if nested_secrets:
                secrets[key] = nested_secrets
        else:
            public[key] = value
    return public, secrets


def _fernet(key_material: str) -> Fernet:
    digest = hashlib.sha256(key_material.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _b64decode(data: str) -> bytes:
    return base64.b64decode(data.encode("ascii"))


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_json(payload: dict[str, Any]) -> str:
    return _b64url(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))


def _b64url_decode(data: str) -> str:
    padded = data + "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8")
