"""Source connectors.

Phase 2 implements the shared protocol and the local file-upload connector.
Phase 10 adds website, GitHub, PostgreSQL, and REST API connectors.
"""

from app.connectors.file_upload import FileUploadConnector
from app.connectors.protocol import CanonicalDocument, SourceConnector

__all__ = ["CanonicalDocument", "FileUploadConnector", "SourceConnector"]
