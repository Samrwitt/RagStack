import pytest
from redis import Redis

from app.core.config import get_settings
from tests.integration.services import requires_redis

pytestmark = [pytest.mark.integration, requires_redis]


def test_redis_ping() -> None:
    client = Redis.from_url(get_settings().redis_url)
    try:
        assert client.ping() is True
    finally:
        client.close()
