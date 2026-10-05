import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from b2b_domain.db import Base


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    AWAITING_MAPPING = "awaiting_mapping"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class JobType(StrEnum):
    HEALTHCHECK = "healthcheck"
    IMPORT = "import"


class BatchStatus(StrEnum):
    RECEIVED = "received"
    LOADING = "loading"
    AWAITING_MAPPING = "awaiting_mapping"
    FAILED = "failed"


class ValidationSeverity(StrEnum):
    INFORMATIONAL = "informational"
    WARNING = "warning"
    CRITICAL = "critical"


class ValidationDisposition(StrEnum):
    FLAG = "flag"
    QUARANTINE = "quarantine"
    REJECT = "reject"


class MappingVersionStatus(StrEnum):
    DRAFT = "draft"
    APPROVED = "approved"
    REJECTED = "rejected"


class MappingDecision(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"


class ImportJob(Base):
    __tablename__ = "import_jobs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'running', 'awaiting_mapping', 'succeeded', 'failed')",
            name="ck_import_jobs_status",
        ),
        CheckConstraint(
            "job_type IN ('healthcheck', 'import')",
            name="ck_import_jobs_type",
        ),
        CheckConstraint("char_length(source_sha256) = 64", name="ck_import_jobs_sha256"),
        Index(
            "uq_import_jobs_active_source_sha256",
            "source_sha256",
            unique=True,
            postgresql_where=text("status IN ('queued', 'running', 'awaiting_mapping')"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_type: Mapped[str] = mapped_column(String(32), default=JobType.IMPORT)
    status: Mapped[str] = mapped_column(String(32), default=JobStatus.QUEUED, index=True)
    source_filename: Mapped[str] = mapped_column(String(512))
    source_sha256: Mapped[str] = mapped_column(String(64))
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    original_row_count: Mapped[int | None] = mapped_column(BigInteger)
    accepted_row_count: Mapped[int | None] = mapped_column(BigInteger)
    rejected_row_count: Mapped[int | None] = mapped_column(BigInteger)
    pending_row_count: Mapped[int | None] = mapped_column(BigInteger)
    quarantined_row_count: Mapped[int | None] = mapped_column(BigInteger)
    error_summary: Mapped[dict[str, Any] | None] = mapped_column(JSONB)


class ImportBatch(Base):
    __tablename__ = "import_batches"
    __table_args__ = (
        CheckConstraint(
            "status IN ('received', 'loading', 'awaiting_mapping', 'failed')",
            name="ck_import_batches_status",
        ),
        CheckConstraint("char_length(source_sha256) = 64", name="ck_import_batches_sha256"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    import_job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("import_jobs.id"), index=True
    )
    status: Mapped[str] = mapped_column(String(32), default=BatchStatus.RECEIVED)
    source_filename: Mapped[str] = mapped_column(String(512))
    source_sha256: Mapped[str] = mapped_column(String(64))
    storage_path: Mapped[str] = mapped_column(Text)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    sheet_count: Mapped[int | None] = mapped_column(BigInteger)
    original_row_count: Mapped[int | None] = mapped_column(BigInteger)
    pending_row_count: Mapped[int | None] = mapped_column(BigInteger)
    quarantined_row_count: Mapped[int | None] = mapped_column(BigInteger)
    rejected_row_count: Mapped[int | None] = mapped_column(BigInteger)
    error_summary: Mapped[dict[str, Any] | None] = mapped_column(JSONB)


class SourceProfile(Base):
    __tablename__ = "source_profiles"
    __table_args__ = (
        CheckConstraint("row_count >= 0", name="ck_source_profiles_row_count"),
        CheckConstraint("field_count >= 0", name="ck_source_profiles_field_count"),
        Index(
            "uq_source_profiles_batch_source",
            "import_batch_id",
            "source_name",
            unique=True,
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    import_batch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("import_batches.id"), index=True
    )
    source_name: Mapped[str] = mapped_column(String(512))
    row_count: Mapped[int] = mapped_column(BigInteger)
    field_count: Mapped[int] = mapped_column(BigInteger)
    field_profiles: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    profiled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

class RawSourceRow(Base):
    __tablename__ = "raw_source_rows"
    __table_args__ = (
        CheckConstraint(
            "validation_status IN ('pending', 'accepted', 'quarantined', 'rejected')",
            name="ck_raw_source_rows_validation_status",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    import_job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("import_jobs.id"), index=True
    )
    import_batch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("import_batches.id"), index=True
    )
    source_filename: Mapped[str] = mapped_column(String(512))
    source_sha256: Mapped[str] = mapped_column(String(64))
    source_name: Mapped[str] = mapped_column(String(512))
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    original_row_number: Mapped[int] = mapped_column(BigInteger)
    raw_payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    validation_status: Mapped[str] = mapped_column(String(32), default="pending")
    validation_errors: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    error_reason: Mapped[str | None] = mapped_column(Text)


class ImportValidationIssue(Base):
    __tablename__ = "import_validation_issues"
    __table_args__ = (
        CheckConstraint(
            "severity IN ('informational', 'warning', 'critical')",
            name="ck_import_validation_issues_severity",
        ),
        CheckConstraint(
            "disposition IN ('flag', 'quarantine', 'reject')",
            name="ck_import_validation_issues_disposition",
        ),
        CheckConstraint(
            "original_row_number IS NULL OR original_row_number > 0",
            name="ck_import_validation_issues_row_number",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    import_batch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("import_batches.id"), index=True
    )
    raw_source_row_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("raw_source_rows.id"), index=True
    )
    source_name: Mapped[str] = mapped_column(String(512))
    original_row_number: Mapped[int | None] = mapped_column(BigInteger)
    severity: Mapped[str] = mapped_column(String(32))
    code: Mapped[str] = mapped_column(String(128))
    field_name: Mapped[str | None] = mapped_column(String(512))
    detail: Mapped[str] = mapped_column(Text)
    disposition: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class MappingVersion(Base):
    __tablename__ = "mapping_versions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'approved', 'rejected')",
            name="ck_mapping_versions_status",
        ),
        CheckConstraint("version > 0", name="ck_mapping_versions_version"),
        Index(
            "uq_mapping_versions_batch_source_version",
            "import_batch_id",
            "source_name",
            "version",
            unique=True,
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    import_batch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("import_batches.id"), index=True
    )
    source_name: Mapped[str] = mapped_column(String(512))
    version: Mapped[int] = mapped_column(BigInteger)
    canonical_entity: Mapped[str] = mapped_column(String(64))
    field_mappings: Mapped[dict[str, str]] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(32), default=MappingVersionStatus.DRAFT)
    created_by: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    reviewed_by: Mapped[str | None] = mapped_column(String(128))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_note: Mapped[str | None] = mapped_column(Text)


class MappingReviewDecision(Base):
    __tablename__ = "mapping_review_decisions"
    __table_args__ = (
        CheckConstraint(
            "decision IN ('approve', 'reject')", name="ck_mapping_review_decisions_decision"
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    mapping_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("mapping_versions.id"), index=True
    )
    decision: Mapped[str] = mapped_column(String(32))
    actor: Mapped[str] = mapped_column(String(128))
    note: Mapped[str | None] = mapped_column(Text)
    decided_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class MappingActivation(Base):
    __tablename__ = "mapping_activations"
    __table_args__ = (
        CheckConstraint(
            "evidence_kind = 'real_anonymized'",
            name="ck_mapping_activations_real_evidence",
        ),
        CheckConstraint(
            "judgment IN ('Pass', 'Conditional Pass')",
            name="ck_mapping_activations_judgment",
        ),
        CheckConstraint(
            "char_length(evidence_sha256) = 64",
            name="ck_mapping_activations_sha256",
        ),
        UniqueConstraint("mapping_version_id", name="uq_mapping_activations_mapping_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    mapping_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("mapping_versions.id"), index=True
    )
    evidence_kind: Mapped[str] = mapped_column(String(32))
    judgment: Mapped[str] = mapped_column(String(32))
    evidence_sha256: Mapped[str] = mapped_column(String(64))
    activated_by: Mapped[str] = mapped_column(String(128))
    activated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    note: Mapped[str | None] = mapped_column(Text)


class CanonicalRecord(Base):
    __tablename__ = "canonical_records"
    __table_args__ = (
        UniqueConstraint(
            "mapping_activation_id",
            "raw_source_row_id",
            name="uq_canonical_records_activation_raw_row",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    mapping_activation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("mapping_activations.id"), index=True
    )
    raw_source_row_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("raw_source_rows.id"), index=True
    )
    canonical_entity: Mapped[str] = mapped_column(String(64))
    canonical_payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    promoted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
