"""Enable PostgreSQL extensions required by CorpusForge.

Revision ID: 0001_enable_extensions
Revises:
Create Date: 2026-08-24

gen_random_uuid() (pgcrypto) is the default for UUID primary keys.
uuid-ossp is enabled for environments that prefer uuid_generate_v4().
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0001_enable_extensions"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')


def downgrade() -> None:
    op.execute('DROP EXTENSION IF EXISTS "uuid-ossp"')
    op.execute("DROP EXTENSION IF EXISTS pgcrypto")
