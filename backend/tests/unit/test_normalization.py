"""Unicode, whitespace, boilerplate, language, and SimHash fingerprints."""

import unicodedata

from app.normalization.boilerplate import is_boilerplate
from app.normalization.language import detect_language
from app.normalization.models import BlockSnapshot
from app.normalization.pipeline import normalize_blocks
from app.normalization.simhash import hamming_distance, simhash64
from app.normalization.text import normalize_text, normalized_content_hash


def test_unicode_nfc_and_entities_without_lowercasing() -> None:
    decomposed = "caf" + "e\u0301"
    composed = unicodedata.normalize("NFC", decomposed)
    cleaned = normalize_text(f"  {decomposed}&nbsp;Policy \r\n Leave  ")
    assert cleaned == f"{composed} Policy Leave"
    assert "Policy" in cleaned
    assert "policy" not in cleaned.replace("Policy", "")


def test_code_preserves_indentation() -> None:
    result = normalize_blocks(
        [
            BlockSnapshot(
                ordinal=0,
                block_type="code",
                text="  def ping():\r\n      return True\r\n",
            )
        ]
    )
    assert result.blocks[0].normalized_text == "  def ping():\n      return True"
    assert not result.blocks[0].dropped


def test_empty_and_boilerplate_blocks_are_dropped() -> None:
    result = normalize_blocks(
        [
            BlockSnapshot(ordinal=0, block_type="title", text="Leave Policy"),
            BlockSnapshot(ordinal=1, block_type="paragraph", text="   "),
            BlockSnapshot(ordinal=2, block_type="paragraph", text="Skip to main content"),
            BlockSnapshot(
                ordinal=3,
                block_type="paragraph",
                text="Employees receive 22 days annual leave.",
            ),
        ]
    )
    dropped = {block.drop_reason for block in result.blocks if block.dropped}
    assert dropped == {"empty", "boilerplate"}
    kept = [block for block in result.blocks if not block.dropped]
    assert [block.normalized_text for block in kept] == [
        "Leave Policy",
        "Employees receive 22 days annual leave.",
    ]
    assert not is_boilerplate(
        "This document describes our privacy policy for customer data.",
        "paragraph",
    )


def test_repeated_headers_across_pages_are_dropped() -> None:
    result = normalize_blocks(
        [
            BlockSnapshot(
                ordinal=0, block_type="paragraph", text="Acme Confidential", page=1
            ),
            BlockSnapshot(ordinal=1, block_type="paragraph", text="Body page one", page=1),
            BlockSnapshot(
                ordinal=2, block_type="paragraph", text="Acme Confidential", page=2
            ),
            BlockSnapshot(ordinal=3, block_type="paragraph", text="Body page two", page=2),
        ]
    )
    headers = [
        block
        for block in result.blocks
        if block.drop_reason == "header"
    ]
    assert len(headers) == 2
    assert result.kept == 2


def test_language_english_vs_french() -> None:
    english = (
        "Employees receive annual leave and must submit requests to HR "
        "for each period that they are away from the office."
    )
    french = (
        "Les employés reçoivent des jours de congés et doivent déposer "
        "une demande pour chaque période dans l'entreprise."
    )
    assert detect_language(english) == "en"
    assert detect_language(french) == "fr"


def test_exact_normalized_hash_ignores_unicode_noise() -> None:
    left = normalize_text("Employees receive 22 days annual leave.")
    right = normalize_text("Employees\u00a0receive   22 days annual leave.")
    assert left == right
    assert normalized_content_hash([left]) == normalized_content_hash([right])


def test_normalized_hash_ignores_filename_titles() -> None:
    body = "Employees receive 22 days annual leave each calendar year."
    left = normalize_blocks(
        [
            BlockSnapshot(ordinal=0, block_type="title", text="handbook"),
            BlockSnapshot(ordinal=1, block_type="paragraph", text=body),
        ]
    )
    right = normalize_blocks(
        [
            BlockSnapshot(ordinal=0, block_type="title", text="leave-policy"),
            BlockSnapshot(ordinal=1, block_type="paragraph", text=body),
        ]
    )
    assert left.content_hash == right.content_hash
    assert left.simhash == right.simhash


def test_simhash_near_duplicates_are_close() -> None:
    base = (
        "The employee handbook describes annual leave policy in detail. "
        "Employees receive 22 days annual leave each calendar year. "
        "Requests must go through HR before travel is booked. "
        "Unused days may carry over subject to manager approval."
    )
    near = (
        "The employee handbook describes annual leave policy in detail. "
        "Employees receive 22 days annual leave each calendar year. "
        "Requests should go through HR before travel is booked. "
        "Unused days may carry over subject to manager approval."
    )
    far = (
        "Redis cluster failover is triggered when a majority of sentinels "
        "agree the master is unreachable. Operators then promote a replica "
        "and update DNS records for the cache endpoint."
    )
    assert hamming_distance(simhash64(base), simhash64(near)) <= 3
    assert hamming_distance(simhash64(base), simhash64(far)) > 3
