"""Initial schema for documents and extractions."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0001_init"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    status_enum = sa.Enum("pending", "processing", "completed", "failed", name="document_status")

    op.create_table(
        "documents",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column("status", status_enum, nullable=False, server_default="pending"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("bucket", sa.String(length=63), nullable=False, server_default="uploads"),
        sa.Column("object_key", sa.String(length=512), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "extractions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("document_id", sa.String(length=36), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("model_used", sa.String(length=80), nullable=False),
        sa.Column("clauses", sa.JSON(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("artifact_bucket", sa.String(length=63), nullable=False, server_default="extractions"),
        sa.Column("artifact_key", sa.String(length=512), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_extractions_document_created", "extractions", ["document_id", "created_at"])


def downgrade() -> None:
    op.drop_index("idx_extractions_document_created", table_name="extractions")
    op.drop_table("extractions")
    op.drop_table("documents")
    op.execute("DROP TYPE IF EXISTS document_status")
