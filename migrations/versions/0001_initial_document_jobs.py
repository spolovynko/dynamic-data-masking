"""initial document jobs

Revision ID: 0001_initial_document_jobs
Revises:
Create Date: 2026-04-28
"""

import sqlalchemy as sa
from alembic import op

revision = "0001_initial_document_jobs"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "document_jobs",
        sa.Column("job_id", sa.String(length=32), primary_key=True),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("original_filename", sa.Text(), nullable=False),
        sa.Column("original_object_key", sa.Text(), nullable=False),
        sa.Column("file_type", sa.String(length=32), nullable=False),
        sa.Column("content_type", sa.Text(), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("redacted_object_key", sa.Text(), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("owner_user_id", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_document_jobs_status", "document_jobs", ["status"])
    op.create_index("ix_document_jobs_file_type", "document_jobs", ["file_type"])
    op.create_index("ix_document_jobs_owner_user_id", "document_jobs", ["owner_user_id"])


def downgrade() -> None:
    op.drop_index("ix_document_jobs_owner_user_id", table_name="document_jobs")
    op.drop_index("ix_document_jobs_file_type", table_name="document_jobs")
    op.drop_index("ix_document_jobs_status", table_name="document_jobs")
    op.drop_table("document_jobs")
