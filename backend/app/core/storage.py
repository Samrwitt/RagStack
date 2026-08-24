"""S3-compatible object storage (MinIO locally, S3 in production).

Raw source bytes are stored before any parsing so ingestion is replayable
without re-fetching upstream systems.
"""

from dataclasses import dataclass
from io import BytesIO
from urllib.parse import urlparse

from minio import Minio
from minio.error import S3Error

from app.core.config import Settings, get_settings


def raw_object_key(
    *,
    source: str,
    document_id: str,
    version: int,
    filename: str,
) -> str:
    """Stable object key for an original source artifact.

    Example: raw/github/<document-id>/v1/original.md
    """
    safe_source = source.strip("/").replace("..", "")
    safe_doc = document_id.strip("/").replace("..", "")
    safe_name = filename.strip("/").replace("..", "")
    return f"raw/{safe_source}/{safe_doc}/v{version}/{safe_name}"


def parse_s3_endpoint(endpoint_url: str) -> tuple[str, bool]:
    """Return (host:port, secure) for the MinIO/S3 client."""
    parsed = urlparse(endpoint_url)
    if parsed.scheme and parsed.netloc:
        host = parsed.netloc
        secure = parsed.scheme == "https"
        return host, secure
    return endpoint_url.rstrip("/"), False


@dataclass(frozen=True, slots=True)
class StoredObject:
    bucket: str
    key: str
    etag: str | None
    size: int


class ObjectStorage:
    """Thin wrapper around an S3-compatible API.

    Kept explicit so later phases can swap credentials, add encryption, or
    inject a fake for tests without hiding the storage contract.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        cfg = settings or get_settings()
        host, parsed_secure = parse_s3_endpoint(cfg.s3_endpoint_url)
        secure = cfg.s3_use_tls if cfg.s3_secure is not None else parsed_secure
        self._bucket = cfg.s3_bucket
        self._client = Minio(
            host,
            access_key=cfg.s3_access_key,
            secret_key=cfg.s3_secret_key,
            secure=secure,
            region=cfg.s3_region,
        )

    @property
    def bucket(self) -> str:
        return self._bucket

    def bucket_exists(self) -> bool:
        return bool(self._client.bucket_exists(self._bucket))

    def ensure_bucket(self) -> None:
        if not self.bucket_exists():
            self._client.make_bucket(self._bucket)

    def put_bytes(
        self,
        key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> StoredObject:
        result = self._client.put_object(
            self._bucket,
            key,
            BytesIO(data),
            length=len(data),
            content_type=content_type,
        )
        return StoredObject(
            bucket=self._bucket,
            key=key,
            etag=getattr(result, "etag", None),
            size=len(data),
        )

    def get_bytes(self, key: str) -> bytes:
        response = self._client.get_object(self._bucket, key)
        try:
            return bytes(response.read())
        finally:
            response.close()
            response.release_conn()

    def exists(self, key: str) -> bool:
        try:
            self._client.stat_object(self._bucket, key)
            return True
        except S3Error as exc:
            if exc.code in {"NoSuchKey", "NoSuchObject"}:
                return False
            raise

    def ping(self) -> None:
        if not self.bucket_exists():
            raise RuntimeError(f"object storage bucket {self._bucket!r} does not exist")


_storage: ObjectStorage | None = None


def get_object_storage(settings: Settings | None = None) -> ObjectStorage:
    global _storage
    if _storage is None:
        _storage = ObjectStorage(settings)
    return _storage
