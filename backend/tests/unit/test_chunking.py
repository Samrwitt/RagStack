"""Unit tests for fixed, recursive, heading-aware, and parent-child chunkers."""

from app.chunking.fixed import chunk_fixed
from app.chunking.models import BlockInput, ChunkKind, ChunkStrategy
from app.chunking.parent_child import chunk_parent_child
from app.chunking.recursive import chunk_recursive
from app.chunking.registry import run_chunker
from app.chunking.structure import chunk_heading_aware
from app.chunking.tokens import count_tokens


def test_fixed_chunking_respects_size_and_overlap() -> None:
    tokens = [f"w{i}" for i in range(20)]
    text = " ".join(tokens)
    chunks = chunk_fixed(text, chunk_size=8, overlap=2)
    assert len(chunks) >= 3
    assert all(c.token_count <= 8 for c in chunks)
    # Overlap: first window ends at w7, second starts at w6
    assert chunks[0].text.startswith("w0")
    assert "w6" in chunks[1].text and "w7" in chunks[1].text


def test_recursive_prefers_paragraph_boundaries() -> None:
    text = (
        "First paragraph talks about annual leave policy for employees.\n\n"
        "Second paragraph covers the request workflow through HR desks.\n\n"
        "Third paragraph explains carry-over caps and manager approval."
    )
    chunks = chunk_recursive(text, chunk_size=20, overlap=2)
    assert len(chunks) >= 2
    allowed = {"paragraph", "sentence", "token", "whole", "line"}
    assert all(c.metadata.get("split") in allowed for c in chunks)
    joined = " ".join(c.text for c in chunks)
    assert "annual leave" in joined
    assert "carry-over" in joined


def test_heading_aware_keeps_section_metadata() -> None:
    blocks = [
        BlockInput(0, "title", "Handbook"),
        BlockInput(1, "heading", "Leave", heading_level=2, section="Leave"),
        BlockInput(2, "paragraph", "Employees receive 22 days annual leave.", section="Leave"),
        BlockInput(3, "heading", "Remote work", heading_level=2, section="Remote work"),
        BlockInput(
            4,
            "paragraph",
            "Employees may work remotely two days each week.",
            section="Remote work",
        ),
        BlockInput(5, "table", "| Day | Cap |\n| --- | --- |\n| Mon | 2 |", section="Remote work"),
    ]
    result = chunk_heading_aware(blocks, chunk_size=64, overlap=8)
    assert result.strategy is ChunkStrategy.HEADING_AWARE
    sections = {c.section for c in result.chunks}
    assert "Leave" in sections
    assert "Remote work" in sections
    assert any("22 days" in c.text for c in result.chunks)


def test_parent_child_links_children_to_section_parents() -> None:
    long_body = " ".join(f"sentence{i} about leave policy details." for i in range(40))
    blocks = [
        BlockInput(0, "heading", "Leave Policy", heading_level=1, section="Leave Policy"),
        BlockInput(1, "paragraph", long_body, section="Leave Policy"),
        BlockInput(2, "heading", "Short", heading_level=2, section="Short"),
        BlockInput(3, "paragraph", "Tiny section.", section="Short"),
    ]
    result = chunk_parent_child(blocks, chunk_size=24, overlap=4, parent_max_tokens=200)
    assert result.strategy is ChunkStrategy.PARENT_CHILD
    parents = [c for c in result.chunks if c.kind is ChunkKind.PARENT]
    children = [c for c in result.chunks if c.kind is ChunkKind.CHILD]
    assert parents
    assert children
    assert all(c.parent_index is not None for c in children)
    assert all(result.chunks[c.parent_index].kind is ChunkKind.PARENT for c in children)


def test_run_chunker_registry_default_parent_child() -> None:
    blocks = [
        BlockInput(0, "paragraph", "Employees receive 22 days annual leave each year."),
    ]
    result = run_chunker(blocks, strategy="fixed", chunk_size=16, overlap=2)
    assert result.strategy is ChunkStrategy.FIXED
    assert result.chunks
    assert count_tokens(result.chunks[0].text) <= 16


def test_dropped_blocks_are_ignored() -> None:
    blocks = [
        BlockInput(0, "paragraph", "Skip to main content", dropped=True),
        BlockInput(1, "paragraph", "Employees receive 22 days annual leave."),
    ]
    result = run_chunker(blocks, strategy="recursive", chunk_size=64, overlap=8)
    assert all("Skip to main content" not in c.text for c in result.chunks)
    assert any("22 days" in c.text for c in result.chunks)
