import pytest

from app.core.config import get_settings
from app.core.qdrant import ping_qdrant
from tests.integration.services import requires_qdrant

pytestmark = [pytest.mark.integration, requires_qdrant]


def test_qdrant_lists_collections() -> None:
    count = ping_qdrant(get_settings())
    assert count >= 0
