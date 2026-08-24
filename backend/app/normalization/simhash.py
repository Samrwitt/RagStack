"""64-bit SimHash over word tokens. Fingerprints are not stored text."""

from __future__ import annotations

import hashlib
import re

_TOKEN = re.compile(r"[A-Za-z0-9À-ÿ']+", re.UNICODE)


def tokenize(text: str) -> list[str]:
    return [match.group(0).lower() for match in _TOKEN.finditer(text)]


def simhash64(text: str) -> int:
    tokens = tokenize(text)
    if not tokens:
        return 0
    weights = [0] * 64
    for token in tokens:
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        value = int.from_bytes(digest, "big")
        for bit in range(64):
            weights[bit] += 1 if (value >> bit) & 1 else -1
    fingerprint = 0
    for bit, weight in enumerate(weights):
        if weight >= 0:
            fingerprint |= 1 << bit
    return fingerprint


def hamming_distance(left: int, right: int) -> int:
    return (left ^ right).bit_count()


def as_int64(value: int) -> int:
    """Fit an unsigned 64-bit fingerprint into signed BIGINT."""
    if value >= 2**63:
        return value - 2**64
    return value


def as_uint64(value: int) -> int:
    if value < 0:
        return value + 2**64
    return value


def similarity_score(left: int, right: int) -> float:
    return 1.0 - (hamming_distance(left, right) / 64.0)
