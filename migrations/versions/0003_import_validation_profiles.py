"""Add import profiles, validation issues, and active-import idempotency.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "uq_import_jobs_active_source_sha256",
        "import_jobs",
        ["source_sha256"],
        unique=True,
        postgresql_where=sa.text("status IN ('queued', 'running', 'awaiting_mapping')"),
    )
    op.create_table(
        "source_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("import_batch_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_name", sa.String(length=512), nullable=False),
        sa.Column("row_count", sa.BigInteger(), nullable=False),
        sa.Column("field_count", sa.BigInteger(), nullable=False),
        sa.Column("field_profiles", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "profiled_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("row_count >= 0", name="ck_source_profiles_row_count"),
        sa.CheckConstraint("field_count >= 0", name="ck_source_profiles_field_count"),
        sa.ForeignKeyConstraint(["import_batch_id"], ["import_batches.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "import_batch_id", "source_name", name="uq_source_profiles_batch_source"
        ),
    )
    op.create_index("ix_source_profiles_import_batch_id", "source_profiles", ["import_batch_id"])
    op.create_table(
        "import_validation_issues",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("import_batch_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("raw_source_row_id", sa.BigInteger(), nullable=True),
        sa.Column("source_name", sa.String(length=512), nullable=False),
        sa.Column("original_row_number", sa.BigInteger(), nullable=True),
        sa.Column("severity", sa.String(length=32), nullable=False),
        sa.Column("code", sa.String(length=128), nullable=False),
        sa.Column("field_name", sa.String(length=512), nullable=True),
        sa.Column("detail", sa.Text(), nullable=False),
        sa.Column("disposition", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "severity IN ('informational', 'warning', 'critical')",
            name="ck_import_validation_issues_severity",
        ),
        sa.CheckConstraint(
            "disposition IN ('flag', 'quarantine', 'reject')",
            name="ck_import_validation_issues_disposition",
        ),
        sa.CheckConstraint(
            "original_row_number IS NULL OR original_row_number > 0",
            name="ck_import_validation_issues_row_number",
        ),
        sa.ForeignKeyConstraint(["import_batch_id"], ["import_batches.id"]),
        sa.ForeignKeyConstraint(["raw_source_row_id"], ["raw_source_rows.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_import_validation_issues_import_batch_id",
        "import_validation_issues",
        ["import_batch_id"],
    )
    op.create_index(
        "ix_import_validation_issues_raw_source_row_id",
        "import_validation_issues",
        ["raw_source_row_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_import_validation_issues_raw_source_row_id", table_name="import_validation_issues"
    )
    op.drop_index(
        "ix_import_validation_issues_import_batch_id", table_name="import_validation_issues"
    )
    op.drop_table("import_validation_issues")
    op.drop_index("ix_source_profiles_import_batch_id", table_name="source_profiles")
    op.drop_table("source_profiles")
    op.drop_index("uq_import_jobs_active_source_sha256", table_name="import_jobs")
