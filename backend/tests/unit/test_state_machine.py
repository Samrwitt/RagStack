import pytest

from app.ingestion.state_machine import InvalidStateTransition, can_transition, transition
from app.models.enums import DocumentState


def test_happy_path_to_chunked() -> None:
    state = DocumentState.DISCOVERED
    state = transition(state, DocumentState.FETCHING)
    state = transition(state, DocumentState.FETCHED)
    state = transition(state, DocumentState.PARSING)
    state = transition(state, DocumentState.PARSED)
    state = transition(state, DocumentState.NORMALIZING)
    state = transition(state, DocumentState.NORMALIZED)
    state = transition(state, DocumentState.CHUNKING)
    state = transition(state, DocumentState.CHUNKED)
    assert state is DocumentState.CHUNKED


def test_parsed_can_reparse_without_refetch() -> None:
    assert can_transition(DocumentState.PARSED, DocumentState.PARSING)


def test_normalized_can_reparse_and_renormalize() -> None:
    assert can_transition(DocumentState.NORMALIZED, DocumentState.PARSING)
    assert can_transition(DocumentState.NORMALIZED, DocumentState.NORMALIZING)


def test_chunked_can_rechunk() -> None:
    assert can_transition(DocumentState.CHUNKED, DocumentState.CHUNKING)
    assert can_transition(DocumentState.CHUNKED, DocumentState.PARSING)


def test_embedding_and_indexing_recover_from_failure() -> None:
    assert can_transition(DocumentState.FAILED, DocumentState.EMBEDDING)
    assert can_transition(DocumentState.FAILED, DocumentState.INDEXING)


def test_indexed_can_reembed() -> None:
    assert can_transition(DocumentState.INDEXED, DocumentState.EMBEDDING)


def test_fetched_can_refetch_on_content_change() -> None:
    assert can_transition(DocumentState.FETCHED, DocumentState.FETCHING)


def test_deleted_is_terminal() -> None:
    assert can_transition(DocumentState.FETCHED, DocumentState.DELETED)
    assert not can_transition(DocumentState.DELETED, DocumentState.FETCHING)


def test_invalid_transition_raises() -> None:
    with pytest.raises(InvalidStateTransition):
        transition(DocumentState.DISCOVERED, DocumentState.INDEXED)
