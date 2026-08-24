"""Document chunks produced by Phase 5 strategies.

Revision ID: 0005_document_chunks
Revises: 0004_normalization
Create Date: 2026-08-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_document_chunks"
down_revision: str | Sequence[str] | None = "0004_normalization"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSONB = postgresql.JSONB(astext_type=sa.Text())
UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.add_column(
        "document_versions",
        sa.Column("chunk_strategy", sa.String(32), nullable=True),
    )
    op.add_column(
        "document_versions",
        sa.Column("chunker_version", sa.Integer(), nullable=True),
    )
    op.add_column(
        "document_versions",
        sa.Column("chunk_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "document_versions",
        sa.Column("chunked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "document_chunks",
        sa.Column("id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("document_id", UUID, sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("version_id", UUID, sa.ForeignKey("document_versions.id"), nullable=False),
        sa.Column(
            "parent_chunk_id",
            UUID,
            sa.ForeignKey("document_chunks.id"),
            nullable=True,
        ),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("page", sa.Integer(), nullable=True),
        sa.Column("section", sa.String(512), nullable=True),
        sa.Column("strategy", sa.String(32), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False, server_default="leaf"),
        sa.Column("extra", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("version_id", "ordinal", name="uq_document_chunk_ordinal"),
    )
    op.create_index("ix_document_chunks_document_id", "document_chunks", ["document_id"])
    op.create_index("ix_document_chunks_version_id", "document_chunks", ["version_id"])
    op.create_index(
        "ix_document_chunks_parent_chunk_id",
        "document_chunks",
        ["parent_chunk_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_document_chunks_parent_chunk_id", table_name="document_chunks")
    op.drop_index("ix_document_chunks_version_id", table_name="document_chunks")
    op.drop_index("ix_document_chunks_document_id", table_name="document_chunks")
    op.drop_table("document_chunks")
    op.drop_column("document_versions", "chunked_at")
    op.drop_column("document_versions", "chunk_count")
    op.drop_column("document_versions", "chunker_version")
    op.drop_column("document_versions", "chunk_strategy")
