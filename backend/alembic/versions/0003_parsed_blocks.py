"""Parsed blocks and parser metadata on document versions.

Revision ID: 0003_parsed_blocks
Revises: 0002_ingestion_control_plane
Create Date: 2026-08-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_parsed_blocks"
down_revision: str | Sequence[str] | None = "0002_ingestion_control_plane"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSONB = postgresql.JSONB(astext_type=sa.Text())
UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.add_column("document_versions", sa.Column("parser_name", sa.String(64), nullable=True))
    op.add_column("document_versions", sa.Column("parser_version", sa.Integer(), nullable=True))
    op.add_column(
        "document_versions",
        sa.Column("used_ocr", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "document_versions",
        sa.Column("parsed_block_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "document_versions",
        sa.Column("parse_warnings", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
    )
    op.add_column("document_versions", sa.Column("parsed_at", sa.DateTime(timezone=True), nullable=True))
    op.create_table(
        "document_blocks",
        sa.Column("id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("document_id", UUID, sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("version_id", UUID, sa.ForeignKey("document_versions.id"), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("block_type", sa.String(32), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("heading_level", sa.Integer(), nullable=True),
        sa.Column("page", sa.Integer(), nullable=True),
        sa.Column("section", sa.String(512), nullable=True),
        sa.Column("extra", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("version_id", "ordinal", name="uq_document_block_ordinal"),
    )
    op.create_index("ix_document_blocks_document_id", "document_blocks", ["document_id"])
    op.create_index("ix_document_blocks_version_id", "document_blocks", ["version_id"])


def downgrade() -> None:
    op.drop_index("ix_document_blocks_version_id", table_name="document_blocks")
    op.drop_index("ix_document_blocks_document_id", table_name="document_blocks")
    op.drop_table("document_blocks")
    op.drop_column("document_versions", "parsed_at")
    op.drop_column("document_versions", "parse_warnings")
    op.drop_column("document_versions", "parsed_block_count")
    op.drop_column("document_versions", "used_ocr")
    op.drop_column("document_versions", "parser_version")
    op.drop_column("document_versions", "parser_name")
