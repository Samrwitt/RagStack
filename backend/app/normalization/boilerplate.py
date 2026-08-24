"""Drop chrome, not policy. Short matching blocks only; titles/code stay."""

from __future__ import annotations

import re
from collections import Counter

from app.normalization.models import BlockSnapshot

_SHORT = 120
_DROP_TYPES = {"paragraph", "list", "quote", "image_caption"}
_PAGE_TYPES = {"paragraph", "heading"}

_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"^skip to (main )?content$",
        r"^all rights reserved\.?$",
        r"^copyright ©?\s?\d{4}.*$",
        r"^cookies? (policy|notice|settings|consent).*$",
        r"^(subscribe|sign up) (to|for) (our )?newsletter.*$",
        r"^this website uses cookies.*$",
        r"^privacy policy$",
        r"^terms of (use|service)$",
        r"^home\s*[|/>•·]\s*about(\s*[|/>•·]\s*contact)?$",
        r"^click here$",
    )
)


def is_boilerplate(text: str, block_type: str) -> bool:
    if block_type not in _DROP_TYPES:
        return False
    stripped = text.strip()
    if not stripped or len(stripped) > _SHORT:
        return False
    return any(pattern.match(stripped) for pattern in _PATTERNS)


def drop_repeated_headers_footers(blocks: list[BlockSnapshot]) -> None:
    pages = sorted({block.page for block in blocks if block.page is not None})
    if len(pages) < 2:
        return
    first_by_page: dict[int, str] = {}
    last_by_page: dict[int, str] = {}
    first_block: dict[int, BlockSnapshot] = {}
    last_block: dict[int, BlockSnapshot] = {}
    for page in pages:
        ordered = [
            block
            for block in blocks
            if block.page == page
            and not block.dropped
            and block.block_type in _PAGE_TYPES
            and block.normalized_text
        ]
        if not ordered:
            continue
        first_by_page[page] = ordered[0].normalized_text or ""
        last_by_page[page] = ordered[-1].normalized_text or ""
        first_block[page] = ordered[0]
        last_block[page] = ordered[-1]
    _drop_repeated(first_by_page, first_block, "header")
    _drop_repeated(last_by_page, last_block, "footer")


def _drop_repeated(
    by_page: dict[int, str],
    owners: dict[int, BlockSnapshot],
    reason: str,
) -> None:
    counts = Counter(text for text in by_page.values() if text)
    repeated = {text for text, count in counts.items() if count >= 2}
    for page, text in by_page.items():
        if text in repeated:
            block = owners[page]
            block.dropped = True
            block.drop_reason = reason
