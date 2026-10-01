import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, String, Text, func
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
