"""Control-plane enumerations stored as strings (not native PG enums).

String storage keeps Alembic migrations additive when new states appear.
"""

from enum import StrEnum


class Role(StrEnum):
    OWNER = "OWNER"
    ADMIN = "ADMIN"
    EDITOR = "EDITOR"
    MEMBER = "MEMBER"
    VIEWER = "VIEWER"


class SourceType(StrEnum):
    FILE_UPLOAD = "file_upload"
    WEBSITE = "website"
    GITHUB = "github"
    POSTGRES = "postgres"
    REST_API = "rest_api"
    GOOGLE_DRIVE = "google_drive"
    ARXIV = "arxiv"


class SourceStatus(StrEnum):
    CONNECTED = "CONNECTED"
    PAUSED = "PAUSED"
    DISCONNECTED = "DISCONNECTED"
    ERROR = "ERROR"


class DocumentState(StrEnum):
    DISCOVERED = "DISCOVERED"
    FETCHING = "FETCHING"
    FETCHED = "FETCHED"
    PARSING = "PARSING"
    PARSED = "PARSED"
    NORMALIZING = "NORMALIZING"
    NORMALIZED = "NORMALIZED"
    CHUNKING = "CHUNKING"
    CHUNKED = "CHUNKED"
    EMBEDDING = "EMBEDDING"
    EMBEDDED = "EMBEDDED"
    INDEXING = "INDEXING"
    INDEXED = "INDEXED"
    FAILED = "FAILED"
    DELETED = "DELETED"


class JobType(StrEnum):
    UPLOAD = "UPLOAD"
    SYNC = "SYNC"
    REPROCESS = "REPROCESS"
    DELETE = "DELETE"


class JobStatus(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    SKIPPED_UNCHANGED = "SKIPPED_UNCHANGED"


class FailureKind(StrEnum):
    TEMPORARY = "temporary"
    PERMANENT = "permanent"


class DuplicateKind(StrEnum):
    EXACT = "exact"
    NEAR = "near"
