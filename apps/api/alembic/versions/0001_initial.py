"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-04-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    job_status = sa.Enum("uploaded", "queued", "processing", "completed", "failed", "canceled", name="jobstatus")
    job_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    op.create_table(
        "files",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("original_name", sa.String(length=512), nullable=False),
        sa.Column("storage_path", sa.String(length=1024), nullable=False),
        sa.Column("mime_type", sa.String(length=128), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_files_user_id"), "files", ["user_id"])

    op.create_table(
        "jobs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("file_id", sa.String(length=36), nullable=False),
        sa.Column("mode", sa.String(length=64), nullable=False),
        sa.Column("output_format", sa.String(length=32), nullable=False),
        sa.Column("template_type", sa.String(length=64), nullable=True),
        sa.Column("status", job_status, nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["file_id"], ["files.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_jobs_file_id"), "jobs", ["file_id"])
    op.create_index(op.f("ix_jobs_status"), "jobs", ["status"])
    op.create_index(op.f("ix_jobs_user_id"), "jobs", ["user_id"])

    op.create_table(
        "page_results",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("job_id", sa.String(length=36), nullable=False),
        sa.Column("page_no", sa.Integer(), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("raw_markdown", sa.Text(), nullable=False),
        sa.Column("reviewed_text", sa.Text(), nullable=False),
        sa.Column("reviewed_markdown", sa.Text(), nullable=False),
        sa.Column("confidence_summary", sa.JSON(), nullable=False),
        sa.Column("is_confirmed", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id", "page_no", name="uq_page_result_job_page"),
    )
    op.create_index(op.f("ix_page_results_job_id"), "page_results", ["job_id"])

    op.create_table(
        "structured_results",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("job_id", sa.String(length=36), nullable=False),
        sa.Column("template_type", sa.String(length=64), nullable=True),
        sa.Column("raw_json", sa.JSON(), nullable=False),
        sa.Column("reviewed_json", sa.JSON(), nullable=False),
        sa.Column("is_confirmed", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_structured_results_job_id"), "structured_results", ["job_id"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_structured_results_job_id"), table_name="structured_results")
    op.drop_table("structured_results")
    op.drop_index(op.f("ix_page_results_job_id"), table_name="page_results")
    op.drop_table("page_results")
    op.drop_index(op.f("ix_jobs_user_id"), table_name="jobs")
    op.drop_index(op.f("ix_jobs_status"), table_name="jobs")
    op.drop_index(op.f("ix_jobs_file_id"), table_name="jobs")
    op.drop_table("jobs")
    op.drop_index(op.f("ix_files_user_id"), table_name="files")
    op.drop_table("files")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
    sa.Enum(name="jobstatus").drop(op.get_bind(), checkfirst=True)
