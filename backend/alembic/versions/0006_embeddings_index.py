"""Embedding records and vector index metadata.

Revision ID: 0006_embeddings_index
Revises: 0005_document_chunks
Create Date: 2026-08-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_embeddings_index"
down_revision: str | Sequence[str] | None = "0005_document_chunks"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSONB = postgresql.JSONB(astext_type=sa.Text())
UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.add_column("document_versions", sa.Column("embedding_provider", sa.String(64)))
    op.add_column("document_versions", sa.Column("embedding_model", sa.String(128)))
    op.add_column("document_versions", sa.Column("embedding_version", sa.Integer()))
    op.add_column("document_versions", sa.Column("embedding_dimension", sa.Integer()))
    op.add_column("document_versions", sa.Column("embedded_at", sa.DateTime(timezone=True)))
    op.add_column("document_versions", sa.Column("indexed_at", sa.DateTime(timezone=True)))
    op.add_column("document_versions", sa.Column("qdrant_collection", sa.String(128)))

    op.create_table(
        "chunk_embeddings",
        sa.Column("id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", UUID, nullable=False),
        sa.Column("document_id", UUID, sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("version_id", UUID, sa.ForeignKey("document_versions.id"), nullable=False),
        sa.Column("chunk_id", UUID, sa.ForeignKey("document_chunks.id"), nullable=False),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("model", sa.String(128), nullable=False),
        sa.Column("embedding_version", sa.Integer(), nullable=False),
        sa.Column("dimensions", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("qdrant_collection", sa.String(128), nullable=False),
        sa.Column("qdrant_point_id", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="EMBEDDED"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("embedded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.UniqueConstraint(
            "chunk_id",
            "provider",
            "model",
            "embedding_version",
            name="uq_chunk_embedding_provider_model_version",
        ),
    )
    op.create_index(
        "ix_chunk_embeddings_org_status",
        "chunk_embeddings",
        ["organization_id", "status"],
    )
    op.create_index("ix_chunk_embeddings_version_id", "chunk_embeddings", ["version_id"])
    op.create_index("ix_chunk_embeddings_point_id", "chunk_embeddings", ["qdrant_point_id"])


def downgrade() -> None:
    op.drop_index("ix_chunk_embeddings_point_id", table_name="chunk_embeddings")
    op.drop_index("ix_chunk_embeddings_version_id", table_name="chunk_embeddings")
    op.drop_index("ix_chunk_embeddings_org_status", table_name="chunk_embeddings")
    op.drop_table("chunk_embeddings")
    op.drop_column("document_versions", "qdrant_collection")
    op.drop_column("document_versions", "indexed_at")
    op.drop_column("document_versions", "embedded_at")
    op.drop_column("document_versions", "embedding_dimension")
    op.drop_column("document_versions", "embedding_version")
    op.drop_column("document_versions", "embedding_model")
    op.drop_column("document_versions", "embedding_provider")
