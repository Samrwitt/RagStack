"""Normalization metadata and duplicate relationships.

Revision ID: 0004_normalization
Revises: 0003_parsed_blocks
Create Date: 2026-08-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_normalization"
down_revision: str | Sequence[str] | None = "0003_parsed_blocks"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.add_column("document_blocks", sa.Column("normalized_text", sa.Text(), nullable=True))
    op.add_column("documents", sa.Column("language", sa.String(16), nullable=True))
    op.add_column(
        "documents",
        sa.Column("canonical_document_id", UUID, sa.ForeignKey("documents.id"), nullable=True),
    )
    op.create_index(
        "ix_documents_canonical_document_id",
        "documents",
        ["canonical_document_id"],
    )
    op.add_column("document_versions", sa.Column("language", sa.String(16), nullable=True))
    op.add_column(
        "document_versions",
        sa.Column("normalized_content_hash", sa.String(64), nullable=True),
    )
    op.create_index(
        "ix_document_versions_normalized_content_hash",
        "document_versions",
        ["normalized_content_hash"],
    )
    op.add_column("document_versions", sa.Column("simhash", sa.BigInteger(), nullable=True))
    op.add_column(
        "document_versions",
        sa.Column("normalizer_name", sa.String(64), nullable=True),
    )
    op.add_column(
        "document_versions",
        sa.Column("normalizer_version", sa.Integer(), nullable=True),
    )
    op.add_column(
        "document_versions",
        sa.Column("normalized_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "document_versions",
        sa.Column("duplicate_kind", sa.String(16), nullable=True),
    )
    op.create_table(
        "document_duplicates",
        sa.Column("id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", UUID, sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("canonical_document_id", UUID, sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("duplicate_document_id", UUID, sa.ForeignKey("documents.id"), nullable=False),
        sa.Column(
            "canonical_version_id",
            UUID,
            sa.ForeignKey("document_versions.id"),
            nullable=False,
        ),
        sa.Column(
            "duplicate_version_id",
            UUID,
            sa.ForeignKey("document_versions.id"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(16), nullable=False, server_default="exact"),
        sa.Column("score", sa.Float(), nullable=False),
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
            "canonical_version_id",
            "duplicate_version_id",
            "kind",
            name="uq_document_duplicate_pair",
        ),
    )
    op.create_index(
        "ix_document_duplicates_organization_id",
        "document_duplicates",
        ["organization_id"],
    )
    op.create_index(
        "ix_document_duplicates_canonical_document_id",
        "document_duplicates",
        ["canonical_document_id"],
    )
    op.create_index(
        "ix_document_duplicates_duplicate_document_id",
        "document_duplicates",
        ["duplicate_document_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_document_duplicates_duplicate_document_id",
        table_name="document_duplicates",
    )
    op.drop_index(
        "ix_document_duplicates_canonical_document_id",
        table_name="document_duplicates",
    )
    op.drop_index(
        "ix_document_duplicates_organization_id",
        table_name="document_duplicates",
    )
    op.drop_table("document_duplicates")
    op.drop_column("document_versions", "duplicate_kind")
    op.drop_column("document_versions", "normalized_at")
    op.drop_column("document_versions", "normalizer_version")
    op.drop_column("document_versions", "normalizer_name")
    op.drop_column("document_versions", "simhash")
    op.drop_index(
        "ix_document_versions_normalized_content_hash",
        table_name="document_versions",
    )
    op.drop_column("document_versions", "normalized_content_hash")
    op.drop_column("document_versions", "language")
    op.drop_index("ix_documents_canonical_document_id", table_name="documents")
    op.drop_column("documents", "canonical_document_id")
    op.drop_column("documents", "language")
    op.drop_column("document_blocks", "normalized_text")
