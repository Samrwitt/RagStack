"""Query transformation strategies: Multi-query expansion and HyDE (Hypothetical Document Embeddings)."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.config import Settings


class QueryTransformer:
    """Provides query expansion and HyDE generation for enhanced retrieval."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings

    def expand_query(self, query: str, max_variations: int = 3) -> list[str]:
        """Generate alternative variations of the search query to improve retrieval recall."""
        variations = [query.strip()]
        cleaned = re.sub(r"[^\w\s]", "", query).strip()

        # Add noun-phrase focus variation if query contains multiple terms
        words = cleaned.split()
        if len(words) > 3:
            variations.append(" ".join(words[:4]))
            variations.append(" ".join(words[-4:]))

        # Add domain keyword variations
        if "how to" in query.lower() or "how do i" in query.lower():
            variations.append(re.sub(r"(?i)how (to|do i)\s*", "", query) + " workflow procedure guide")
        elif "error" in query.lower() or "fail" in query.lower():
            variations.append(query + " fix issue solution troubleshoot")

        # Deduplicate while preserving order
        seen = set()
        unique_variations = []
        for v in variations:
            lowered = v.lower()
            if lowered not in seen and len(unique_variations) < max_variations:
                seen.add(lowered)
                unique_variations.append(v)

        return unique_variations

    def generate_hyde_doc(self, query: str) -> str:
        """Generate a hypothetical document snippet answering the query for dense vector matching."""
        return (
            f"Overview and policy regarding {query}. "
            f"This document describes the key principles, guidelines, requirements, and specifications for {query}. "
            f"Section 1: General definitions and scope. Section 2: Implementation details and procedures."
        )
