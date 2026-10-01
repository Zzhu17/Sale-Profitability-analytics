"""Add import batches and source-level raw lineage.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_import_jobs_status", "import_jobs", type_="check")
    op.create_check_constraint(
        "ck_import_jobs_status",
        "import_jobs",
        "status IN ('queued', 'running', 'awaiting_mapping', 'succeeded', 'failed')",
    )
    op.add_column("import_jobs", sa.Column("pending_row_count", sa.BigInteger()))
    op.add_column("import_jobs", sa.Column("quarantined_row_count", sa.BigInteger()))

    op.create_table(
        "import_batches",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("import_job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("source_filename", sa.String(length=512), nullable=False),
        sa.Column("source_sha256", sa.String(length=64), nullable=False),
        sa.Column("storage_path", sa.Text(), nullable=False),
        sa.Column(
            "uploaded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("sheet_count", sa.BigInteger()),
        sa.Column("original_row_count", sa.BigInteger()),
        sa.Column("pending_row_count", sa.BigInteger()),
        sa.Column("quarantined_row_count", sa.BigInteger()),
        sa.Column("rejected_row_count", sa.BigInteger()),
        sa.Column("error_summary", postgresql.JSONB(astext_type=sa.Text())),
        sa.CheckConstraint(
            "status IN ('received', 'loading', 'awaiting_mapping', 'failed')",
            name="ck_import_batches_status",
        ),
        sa.CheckConstraint(
            "char_length(source_sha256) = 64", name="ck_import_batches_sha256"
        ),
        sa.ForeignKeyConstraint(["import_job_id"], ["import_jobs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_import_batches_import_job_id", "import_batches", ["import_job_id"])

    op.add_column(
        "raw_source_rows",
        sa.Column("import_batch_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "raw_source_rows", sa.Column("source_name", sa.String(length=512), nullable=True)
    )
    op.add_column(
        "raw_source_rows",
        sa.Column(
            "validation_errors",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    op.execute(
        """
        INSERT INTO import_batches (
          id, import_job_id, status, source_filename, source_sha256, storage_path,
          original_row_count, pending_row_count
        )
        SELECT id, id, 'awaiting_mapping', source_filename, source_sha256,
               source_filename, original_row_count, original_row_count
        FROM import_jobs
        ON CONFLICT (id) DO NOTHING
        """
    )
    op.execute("ALTER TABLE raw_source_rows DISABLE TRIGGER raw_source_rows_append_only")
    op.execute(
        """
        UPDATE raw_source_rows
        SET import_batch_id = import_job_id, source_name = source_filename
        WHERE import_batch_id IS NULL
        """
    )
    op.execute("ALTER TABLE raw_source_rows ENABLE TRIGGER raw_source_rows_append_only")
    op.alter_column("raw_source_rows", "import_batch_id", nullable=False)
    op.alter_column("raw_source_rows", "source_name", nullable=False)
    op.create_foreign_key(
        "fk_raw_source_rows_import_batch_id",
        "raw_source_rows",
        "import_batches",
        ["import_batch_id"],
        ["id"],
    )
    op.create_index(
        "ix_raw_source_rows_import_batch_id", "raw_source_rows", ["import_batch_id"]
    )
    op.drop_constraint("uq_raw_source_row_lineage", "raw_source_rows", type_="unique")
    op.create_unique_constraint(
        "uq_raw_source_row_lineage",
        "raw_source_rows",
        ["import_batch_id", "source_name", "original_row_number"],
    )


def downgrade() -> None:
    op.execute(
        "UPDATE import_jobs SET status = 'failed' WHERE status = 'awaiting_mapping'"
    )
    op.drop_constraint("uq_raw_source_row_lineage", "raw_source_rows", type_="unique")
    op.create_unique_constraint(
        "uq_raw_source_row_lineage",
        "raw_source_rows",
        ["import_job_id", "source_filename", "original_row_number"],
    )
    op.drop_index("ix_raw_source_rows_import_batch_id", table_name="raw_source_rows")
    op.drop_constraint(
        "fk_raw_source_rows_import_batch_id", "raw_source_rows", type_="foreignkey"
    )
    op.drop_column("raw_source_rows", "validation_errors")
    op.drop_column("raw_source_rows", "source_name")
    op.drop_column("raw_source_rows", "import_batch_id")
    op.drop_index("ix_import_batches_import_job_id", table_name="import_batches")
    op.drop_table("import_batches")
    op.drop_column("import_jobs", "quarantined_row_count")
    op.drop_column("import_jobs", "pending_row_count")
    op.drop_constraint("ck_import_jobs_status", "import_jobs", type_="check")
    op.create_check_constraint(
        "ck_import_jobs_status",
        "import_jobs",
        "status IN ('queued', 'running', 'succeeded', 'failed')",
    )
