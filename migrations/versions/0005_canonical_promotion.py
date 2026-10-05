"""Add real-data mapping activation and canonical lineage.

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "mapping_activations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("mapping_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evidence_kind", sa.String(length=32), nullable=False),
        sa.Column("judgment", sa.String(length=32), nullable=False),
        sa.Column("evidence_sha256", sa.String(length=64), nullable=False),
        sa.Column("activated_by", sa.String(length=128), nullable=False),
        sa.Column(
            "activated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("note", sa.Text()),
        sa.CheckConstraint(
            "evidence_kind = 'real_anonymized'",
            name="ck_mapping_activations_real_evidence",
        ),
        sa.CheckConstraint(
            "judgment IN ('Pass', 'Conditional Pass')",
            name="ck_mapping_activations_judgment",
        ),
        sa.CheckConstraint(
            "char_length(evidence_sha256) = 64",
            name="ck_mapping_activations_sha256",
        ),
        sa.ForeignKeyConstraint(["mapping_version_id"], ["mapping_versions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "mapping_version_id", name="uq_mapping_activations_mapping_version"
        ),
    )
    op.create_index(
        "ix_mapping_activations_mapping_version_id",
        "mapping_activations",
        ["mapping_version_id"],
    )
    op.create_table(
        "canonical_records",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("mapping_activation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("raw_source_row_id", sa.BigInteger(), nullable=False),
        sa.Column("canonical_entity", sa.String(length=64), nullable=False),
        sa.Column("canonical_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "promoted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["mapping_activation_id"], ["mapping_activations.id"]),
        sa.ForeignKeyConstraint(["raw_source_row_id"], ["raw_source_rows.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "mapping_activation_id",
            "raw_source_row_id",
            name="uq_canonical_records_activation_raw_row",
        ),
    )
    op.create_index(
        "ix_canonical_records_mapping_activation_id",
        "canonical_records",
        ["mapping_activation_id"],
    )
    op.create_index(
        "ix_canonical_records_raw_source_row_id",
        "canonical_records",
        ["raw_source_row_id"],
    )
    op.execute(
        """
        CREATE FUNCTION reject_mapping_activation_mutation() RETURNS trigger AS $$
        BEGIN
          RAISE EXCEPTION 'mapping_activations is append-only';
        END;
        $$ LANGUAGE plpgsql;

        CREATE FUNCTION reject_canonical_record_mutation() RETURNS trigger AS $$
        BEGIN
          RAISE EXCEPTION 'canonical_records is append-only';
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER mapping_activations_append_only
        BEFORE UPDATE OR DELETE ON mapping_activations
        FOR EACH ROW EXECUTE FUNCTION reject_mapping_activation_mutation();

        CREATE TRIGGER canonical_records_append_only
        BEFORE UPDATE OR DELETE ON canonical_records
        FOR EACH ROW EXECUTE FUNCTION reject_canonical_record_mutation();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER canonical_records_append_only ON canonical_records")
    op.execute("DROP TRIGGER mapping_activations_append_only ON mapping_activations")
    op.execute("DROP FUNCTION reject_canonical_record_mutation")
    op.execute("DROP FUNCTION reject_mapping_activation_mutation")
    op.drop_index("ix_canonical_records_raw_source_row_id", table_name="canonical_records")
    op.drop_index(
        "ix_canonical_records_mapping_activation_id", table_name="canonical_records"
    )
    op.drop_table("canonical_records")
    op.drop_index(
        "ix_mapping_activations_mapping_version_id", table_name="mapping_activations"
    )
    op.drop_table("mapping_activations")
