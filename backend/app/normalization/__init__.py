"""Cleaning, Unicode normalization, boilerplate removal, and deduplication.

Phase 4 implements exact SHA-256 duplicates and optional near-duplicate
detection (MinHash/SimHash) without silently deleting related documents.
"""
