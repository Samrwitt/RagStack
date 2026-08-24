"""Lightweight token counting. Deterministic whitespace tokens — no model vocab."""

from __future__ import annotations

import re

_TOKEN = re.compile(r"\S+")
_SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-ZÀ-Ý\"'])")


def tokenize(text: str) -> list[str]:
    return _TOKEN.findall(text)


def count_tokens(text: str) -> int:
    return len(tokenize(text))


def join_tokens(tokens: list[str]) -> str:
    return " ".join(tokens)


def split_sentences(text: str) -> list[str]:
    parts = _SENTENCE.split(text.strip())
    return [part.strip() for part in parts if part.strip()]
