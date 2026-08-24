"""Lightweight language detection via stopword density. Deterministic, no model."""

from __future__ import annotations

from collections import Counter

from app.normalization.simhash import tokenize

_STOPWORDS: dict[str, frozenset[str]] = {
    "en": frozenset(
        {
            "the",
            "and",
            "of",
            "to",
            "in",
            "for",
            "is",
            "on",
            "that",
            "with",
            "as",
            "are",
            "this",
            "be",
            "by",
            "an",
            "or",
            "from",
            "at",
            "which",
            "not",
            "have",
            "it",
            "was",
            "each",
            "must",
            "should",
            "employees",
            "receive",
        }
    ),
    "fr": frozenset(
        {
            "le",
            "la",
            "les",
            "de",
            "des",
            "et",
            "un",
            "une",
            "du",
            "en",
            "que",
            "qui",
            "dans",
            "pour",
            "pas",
            "est",
            "sur",
            "par",
            "plus",
            "avec",
            "au",
            "aux",
            "ce",
            "cette",
        }
    ),
    "de": frozenset(
        {
            "der",
            "die",
            "das",
            "und",
            "den",
            "von",
            "zu",
            "mit",
            "im",
            "ist",
            "auf",
            "für",
            "nicht",
            "ein",
            "eine",
            "dem",
            "des",
            "sich",
            "auch",
            "als",
        }
    ),
    "es": frozenset(
        {
            "el",
            "la",
            "los",
            "las",
            "de",
            "y",
            "en",
            "que",
            "un",
            "una",
            "del",
            "se",
            "por",
            "con",
            "para",
            "no",
            "es",
            "una",
            "al",
            "lo",
        }
    ),
}

_MIN_TOKENS = 8
_MIN_RATIO = 0.06


def detect_language(text: str) -> str:
    tokens = tokenize(text)
    if len(tokens) < _MIN_TOKENS:
        return "und"
    counts = Counter(tokens)
    scores: dict[str, float] = {}
    for lang, words in _STOPWORDS.items():
        hits = sum(counts[token] for token in words)
        scores[lang] = hits / len(tokens)
    language, ratio = max(scores.items(), key=lambda item: item[1])
    if ratio < _MIN_RATIO:
        return "und"
    return language
