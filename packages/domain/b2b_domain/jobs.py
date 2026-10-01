from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from b2b_domain.models import (
    BatchStatus,
    ImportBatch,
    ImportJob,
    JobStatus,
    JobType,
    RawSourceRow,
)
from b2b_domain.source_adapters import adapter_for


@dataclass(frozen=True)
class JobOutcome:
    status: JobStatus
    message: str

    @property
    def succeeded(self) -> bool:
        return self.status == JobStatus.SUCCEEDED


def claim_next_job(session: Session) -> ImportJob | None:
    job = session.scalar(
        select(ImportJob)
        .where(ImportJob.status == JobStatus.QUEUED)
        .order_by(ImportJob.uploaded_at, ImportJob.id)
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    if job is None:
        return None
    job.status = JobStatus.RUNNING
    job.started_at = datetime.now(UTC)
    session.commit()
    return job


def process_job(session: Session, job: ImportJob) -> JobOutcome:
    if job.job_type == JobType.HEALTHCHECK:
        return JobOutcome(JobStatus.SUCCEEDED, "Worker healthcheck completed")
    batch = session.scalar(
        select(ImportBatch).where(ImportBatch.import_job_id == job.id).with_for_update()
    )
    if batch is None:
        return JobOutcome(JobStatus.FAILED, "Import batch is missing")
    batch.status = BatchStatus.LOADING
    records = list(adapter_for(Path(batch.storage_path)).records())
    for record in records:
        session.add(
            RawSourceRow(
                import_job_id=job.id,
                import_batch_id=batch.id,
                source_filename=batch.source_filename,
                source_sha256=batch.source_sha256,
                source_name=record.source_name,
                original_row_number=record.original_row_number,
                raw_payload=dict(record.values),
                validation_status="pending",
                validation_errors=[],
                error_reason=None,
            )
        )
    sheet_count = len({record.source_name for record in records})
    batch.status = BatchStatus.AWAITING_MAPPING
    batch.sheet_count = sheet_count
    batch.original_row_count = len(records)
    batch.pending_row_count = len(records)
    batch.quarantined_row_count = 0
    batch.rejected_row_count = 0
    job.original_row_count = len(records)
    job.pending_row_count = len(records)
    job.accepted_row_count = 0
    job.quarantined_row_count = 0
    job.rejected_row_count = 0
    return JobOutcome(
        JobStatus.AWAITING_MAPPING,
        "Raw records loaded; source-to-canonical mapping awaits D0 approval",
    )


def record_outcome(session: Session, job: ImportJob, outcome: JobOutcome) -> None:
    job.status = outcome.status
    job.completed_at = datetime.now(UTC)
    job.error_summary = (
        {"reason": outcome.message} if outcome.status == JobStatus.FAILED else None
    )
    session.add(job)
    session.commit()
