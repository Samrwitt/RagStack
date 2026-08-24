import pytest
from sqlalchemy import text

from app.core.config import get_settings
from app.core.db import get_sync_engine
from tests.integration.services import requires_postgres

pytestmark = [pytest.mark.integration, requires_postgres]


def test_postgres_accepts_select_1() -> None:
    engine = get_sync_engine(get_settings())
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1"))
        assert result.scalar_one() == 1


def test_postgres_has_pgcrypto() -> None:
    engine = get_sync_engine(get_settings())
    with engine.connect() as conn:
        exists = conn.execute(
            text("SELECT extname FROM pg_extension WHERE extname = 'pgcrypto'")
        ).scalar_one_or_none()
        assert exists == "pgcrypto"
