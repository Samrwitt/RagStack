"""Authenticated user groups.

Revision ID: 0009_auth_groups
Revises: 0008_sparse_chunk_index
Create Date: 2026-08-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009_auth_groups"
down_revision: str | Sequence[str] | None = "0008_sparse_chunk_index"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSONB = postgresql.JSONB(astext_type=sa.Text())


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("groups", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
    )


def downgrade() -> None:
    op.drop_column("users", "groups")
