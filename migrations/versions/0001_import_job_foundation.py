"""Create import job and immutable raw lineage tables.

Revision ID: 0001
Revises:
Create Date: 2026-10-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "import_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("source_filename", sa.String(length=512), nullable=False),
        sa.Column("source_sha256", sa.String(length=64), nullable=False),
        sa.Column(
            "uploaded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("original_row_count", sa.BigInteger(), nullable=True),
        sa.Column("accepted_row_count", sa.BigInteger(), nullable=True),
        sa.Column("rejected_row_count", sa.BigInteger(), nullable=True),
        sa.Column("error_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.CheckConstraint(
            "job_type IN ('healthcheck', 'import')", name="ck_import_jobs_type"
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed')",
            name="ck_import_jobs_status",
        ),
        sa.CheckConstraint("char_length(source_sha256) = 64", name="ck_import_jobs_sha256"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_import_jobs_status", "import_jobs", ["status"])

    op.create_table(
        "raw_source_rows",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("import_job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_filename", sa.String(length=512), nullable=False),
        sa.Column("source_sha256", sa.String(length=64), nullable=False),
        sa.Column(
            "imported_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("original_row_number", sa.BigInteger(), nullable=False),
        sa.Column("raw_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("validation_status", sa.String(length=32), nullable=False),
        sa.Column("error_reason", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "validation_status IN ('pending', 'accepted', 'quarantined', 'rejected')",
            name="ck_raw_source_rows_validation_status",
        ),
        sa.ForeignKeyConstraint(["import_job_id"], ["import_jobs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "import_job_id",
            "source_filename",
            "original_row_number",
            name="uq_raw_source_row_lineage",
        ),
    )
    op.create_index("ix_raw_source_rows_import_job_id", "raw_source_rows", ["import_job_id"])
    op.execute(
        """
        CREATE FUNCTION reject_raw_source_row_mutation() RETURNS trigger AS $$
        BEGIN
          RAISE EXCEPTION 'raw_source_rows is append-only';
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER raw_source_rows_append_only
        BEFORE UPDATE OR DELETE ON raw_source_rows
        FOR EACH ROW EXECUTE FUNCTION reject_raw_source_row_mutation();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER raw_source_rows_append_only ON raw_source_rows")
    op.execute("DROP FUNCTION reject_raw_source_row_mutation")
    op.drop_index("ix_raw_source_rows_import_job_id", table_name="raw_source_rows")
    op.drop_table("raw_source_rows")
    op.drop_index("ix_import_jobs_status", table_name="import_jobs")
    op.drop_table("import_jobs")
