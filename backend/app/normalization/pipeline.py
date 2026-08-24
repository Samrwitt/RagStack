"""Turn parsed blocks into cleaned, language-tagged, fingerprintable text."""

from __future__ import annotations

from app.normalization.boilerplate import drop_repeated_headers_footers, is_boilerplate
from app.normalization.language import detect_language
from app.normalization.models import (
    NORMALIZER_NAME,
    NORMALIZER_VERSION,
    BlockSnapshot,
    NormalizedDocument,
)
from app.normalization.simhash import simhash64
from app.normalization.text import normalize_code, normalize_text, normalized_content_hash


def normalize_blocks(blocks: list[BlockSnapshot]) -> NormalizedDocument:
    warnings: list[str] = []
    for block in blocks:
        preserve = block.block_type in {"list", "table"}
        if block.block_type == "code":
            cleaned = normalize_code(block.text)
        else:
            cleaned = normalize_text(block.text, preserve_newlines=preserve)
        block.normalized_text = cleaned or None
        if not cleaned:
            block.dropped = True
            block.drop_reason = "empty"
            continue
        if is_boilerplate(cleaned, block.block_type):
            block.dropped = True
            block.drop_reason = "boilerplate"

    drop_repeated_headers_footers(blocks)

    kept = [
        block
        for block in blocks
        if not block.dropped and block.normalized_text
    ]
    corpus = "\n".join(block.normalized_text or "" for block in kept)
    if not kept:
        warnings.append("all blocks dropped during normalization")
    return NormalizedDocument(
        blocks=blocks,
        language=detect_language(corpus),
        content_hash=normalized_content_hash(
            [block.normalized_text or "" for block in kept]
        ),
        simhash=simhash64(corpus),
        kept=len(kept),
        dropped=sum(1 for block in blocks if block.dropped),
        warnings=warnings,
        normalizer_name=NORMALIZER_NAME,
        normalizer_version=NORMALIZER_VERSION,
    )
