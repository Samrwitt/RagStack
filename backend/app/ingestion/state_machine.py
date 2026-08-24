"""Document processing state machine.

Transitions are explicit. Callers never assign current_state ad hoc.
UNCHANGED is a job outcome, not a document state — the document stays at
its last successful state when content has not changed.
"""

from app.models.enums import DocumentState

_TERMINAL = {DocumentState.DELETED}

_ALLOWED: dict[DocumentState, frozenset[DocumentState]] = {
    DocumentState.DISCOVERED: frozenset(
        {DocumentState.FETCHING, DocumentState.FAILED, DocumentState.DELETED}
    ),
    DocumentState.FETCHING: frozenset(
        {DocumentState.FETCHED, DocumentState.FAILED, DocumentState.DELETED}
    ),
    DocumentState.FETCHED: frozenset(
        {
            DocumentState.FETCHING,
            DocumentState.PARSING,
            DocumentState.FAILED,
            DocumentState.DELETED,
        }
    ),
    DocumentState.PARSING: frozenset(
        {DocumentState.PARSED, DocumentState.FAILED, DocumentState.DELETED}
    ),
    DocumentState.PARSED: frozenset(
        {
            DocumentState.NORMALIZING,
            DocumentState.PARSING,
            DocumentState.FETCHING,
            DocumentState.FAILED,
            DocumentState.DELETED,
        }
    ),
    DocumentState.NORMALIZING: frozenset(
        {DocumentState.NORMALIZED, DocumentState.FAILED, DocumentState.DELETED}
    ),
    DocumentState.NORMALIZED: frozenset(
        {
            DocumentState.CHUNKING,
            DocumentState.PARSING,
            DocumentState.NORMALIZING,
            DocumentState.FETCHING,
            DocumentState.FAILED,
            DocumentState.DELETED,
        }
    ),
    DocumentState.CHUNKING: frozenset(
        {DocumentState.CHUNKED, DocumentState.FAILED, DocumentState.DELETED}
    ),
    DocumentState.CHUNKED: frozenset(
        {
            DocumentState.EMBEDDING,
            DocumentState.CHUNKING,
            DocumentState.PARSING,
            DocumentState.NORMALIZING,
            DocumentState.FETCHING,
            DocumentState.FAILED,
            DocumentState.DELETED,
        }
    ),
    DocumentState.EMBEDDING: frozenset(
        {DocumentState.EMBEDDED, DocumentState.FAILED, DocumentState.DELETED}
    ),
    DocumentState.EMBEDDED: frozenset(
        {
            DocumentState.INDEXING,
            DocumentState.FETCHING,
            DocumentState.FAILED,
            DocumentState.DELETED,
        }
    ),
    DocumentState.INDEXING: frozenset(
        {DocumentState.INDEXED, DocumentState.FAILED, DocumentState.DELETED}
    ),
    DocumentState.INDEXED: frozenset(
        {
            DocumentState.FETCHING,
            DocumentState.PARSING,
            DocumentState.EMBEDDING,
            DocumentState.INDEXING,
            DocumentState.FAILED,
            DocumentState.DELETED,
        }
    ),
    DocumentState.FAILED: frozenset(
        {
            DocumentState.FETCHING,
            DocumentState.PARSING,
            DocumentState.NORMALIZING,
            DocumentState.CHUNKING,
            DocumentState.EMBEDDING,
            DocumentState.INDEXING,
            DocumentState.DELETED,
        }
    ),
    DocumentState.DELETED: frozenset(),
}

SUCCESS_STATES = frozenset(
    {
        DocumentState.DISCOVERED,
        DocumentState.FETCHED,
        DocumentState.PARSED,
        DocumentState.NORMALIZED,
        DocumentState.CHUNKED,
        DocumentState.EMBEDDED,
        DocumentState.INDEXED,
    }
)


class InvalidStateTransition(ValueError):
    def __init__(self, current: DocumentState, target: DocumentState) -> None:
        self.current = current
        self.target = target
        super().__init__(f"cannot transition from {current} to {target}")


def can_transition(current: DocumentState, target: DocumentState) -> bool:
    if current in _TERMINAL:
        return False
    return target in _ALLOWED[current]


def transition(current: str | DocumentState, target: str | DocumentState) -> DocumentState:
    current_state = DocumentState(current)
    target_state = DocumentState(target)
    if not can_transition(current_state, target_state):
        raise InvalidStateTransition(current_state, target_state)
    return target_state
