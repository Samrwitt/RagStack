"""Domain errors for the ingestion control plane."""


class IngestionError(Exception):
    """Base class for expected ingestion failures."""


class NotFoundError(IngestionError):
    pass


class TenantMismatchError(IngestionError):
    pass


class SourcePausedError(IngestionError):
    pass
