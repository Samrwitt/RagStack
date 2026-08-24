import pytest

from app.core.config import get_settings
from app.core.storage import ObjectStorage, raw_object_key
from tests.integration.services import requires_minio

pytestmark = [pytest.mark.integration, requires_minio]


def test_minio_bucket_exists() -> None:
    storage = ObjectStorage(get_settings())
    assert storage.bucket_exists() is True


def test_minio_put_and_get_roundtrip() -> None:
    storage = ObjectStorage(get_settings())
    key = raw_object_key(
        source="local",
        document_id="phase1-healthcheck",
        version=1,
        filename="probe.txt",
    )
    payload = b"corpusforge-phase1"
    stored = storage.put_bytes(key, payload, content_type="text/plain")
    assert stored.key == key
    assert storage.exists(key) is True
    assert storage.get_bytes(key) == payload
