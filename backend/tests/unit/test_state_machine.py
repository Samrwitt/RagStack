import pytest

from app.ingestion.state_machine import InvalidStateTransition, can_transition, transition
from app.models.enums import DocumentState


def test_happy_path_to_parsed() -> None:
    state = DocumentState.DISCOVERED
    state = transition(state, DocumentState.FETCHING)
    state = transition(state, DocumentState.FETCHED)
    state = transition(state, DocumentState.PARSING)
    state = transition(state, DocumentState.PARSED)
    assert state is DocumentState.PARSED


def test_parsed_can_reparse_without_refetch() -> None:
    assert can_transition(DocumentState.PARSED, DocumentState.PARSING)


def test_fetched_can_refetch_on_content_change() -> None:
    assert can_transition(DocumentState.FETCHED, DocumentState.FETCHING)


def test_deleted_is_terminal() -> None:
    assert can_transition(DocumentState.FETCHED, DocumentState.DELETED)
    assert not can_transition(DocumentState.DELETED, DocumentState.FETCHING)


def test_invalid_transition_raises() -> None:
    with pytest.raises(InvalidStateTransition):
        transition(DocumentState.DISCOVERED, DocumentState.INDEXED)
