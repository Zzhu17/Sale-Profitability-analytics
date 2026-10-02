"""Add versioned mapping proposals and review decisions.

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "mapping_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("import_batch_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_name", sa.String(length=512), nullable=False),
        sa.Column("version", sa.BigInteger(), nullable=False),
        sa.Column("canonical_entity", sa.String(length=64), nullable=False),
        sa.Column("field_mappings", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("reviewed_by", sa.String(length=128)),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("review_note", sa.Text()),
        sa.CheckConstraint(
            "status IN ('draft', 'approved', 'rejected')", name="ck_mapping_versions_status"
        ),
        sa.CheckConstraint("version > 0", name="ck_mapping_versions_version"),
        sa.ForeignKeyConstraint(["import_batch_id"], ["import_batches.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "import_batch_id",
            "source_name",
            "version",
            name="uq_mapping_versions_batch_source_version",
        ),
    )
    op.create_index("ix_mapping_versions_import_batch_id", "mapping_versions", ["import_batch_id"])
    op.create_table(
        "mapping_review_decisions",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("mapping_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column("actor", sa.String(length=128), nullable=False),
        sa.Column("note", sa.Text()),
        sa.Column(
            "decided_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "decision IN ('approve', 'reject')", name="ck_mapping_review_decisions_decision"
        ),
        sa.ForeignKeyConstraint(["mapping_version_id"], ["mapping_versions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_mapping_review_decisions_mapping_version_id",
        "mapping_review_decisions",
        ["mapping_version_id"],
    )
    op.execute(
        """
        CREATE FUNCTION reject_approved_mapping_version_mutation() RETURNS trigger AS $$
        BEGIN
          IF OLD.status = 'approved' THEN
            RAISE EXCEPTION 'approved mapping_versions are immutable';
          END IF;
          IF TG_OP = 'DELETE' THEN
            RETURN OLD;
          END IF;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        CREATE FUNCTION reject_mapping_review_decision_mutation() RETURNS trigger AS $$
        BEGIN
          RAISE EXCEPTION 'mapping_review_decisions are append-only';
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER mapping_versions_approved_immutable
        BEFORE UPDATE OR DELETE ON mapping_versions
        FOR EACH ROW EXECUTE FUNCTION reject_approved_mapping_version_mutation();

        CREATE TRIGGER mapping_review_decisions_append_only
        BEFORE UPDATE OR DELETE ON mapping_review_decisions
        FOR EACH ROW EXECUTE FUNCTION reject_mapping_review_decision_mutation();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER mapping_review_decisions_append_only ON mapping_review_decisions")
    op.execute("DROP TRIGGER mapping_versions_approved_immutable ON mapping_versions")
    op.execute("DROP FUNCTION reject_mapping_review_decision_mutation")
    op.execute("DROP FUNCTION reject_approved_mapping_version_mutation")
    op.drop_index(
        "ix_mapping_review_decisions_mapping_version_id", table_name="mapping_review_decisions"
    )
    op.drop_table("mapping_review_decisions")
    op.drop_index("ix_mapping_versions_import_batch_id", table_name="mapping_versions")
    op.drop_table("mapping_versions")
