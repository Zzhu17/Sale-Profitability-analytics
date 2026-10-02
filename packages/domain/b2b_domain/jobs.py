from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from b2b_domain.ingestion import ImportContractError
from b2b_domain.models import (
    BatchStatus,
    ImportBatch,
    ImportJob,
    ImportValidationIssue,
    JobStatus,
    JobType,
    RawSourceRow,
    SourceProfile,
    ValidationDisposition,
    ValidationSeverity,
)
from b2b_domain.settings import get_settings
from b2b_domain.source_adapters import RawScalar, SourceAdapterError, adapter_for

JOB_TRANSITIONS = {
    JobStatus.QUEUED: frozenset({JobStatus.RUNNING}),
    JobStatus.RUNNING: frozenset(
        {JobStatus.AWAITING_MAPPING, JobStatus.SUCCEEDED, JobStatus.FAILED}
    ),
    JobStatus.AWAITING_MAPPING: frozenset({JobStatus.FAILED}),
    JobStatus.SUCCEEDED: frozenset(),
    JobStatus.FAILED: frozenset(),
}
BATCH_TRANSITIONS = {
    BatchStatus.RECEIVED: frozenset({BatchStatus.LOADING, BatchStatus.FAILED}),
    BatchStatus.LOADING: frozenset({BatchStatus.AWAITING_MAPPING, BatchStatus.FAILED}),
    BatchStatus.AWAITING_MAPPING: frozenset({BatchStatus.FAILED}),
    BatchStatus.FAILED: frozenset(),
}


@dataclass(frozen=True)
class JobOutcome:
    status: JobStatus
    message: str
    error_code: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.status == JobStatus.SUCCEEDED


@dataclass
class FieldProfile:
    name: str
    distinct_value_limit: int
    empty_count: int = 0
    non_empty_count: int = 0
    value_kinds: Counter[str] = field(default_factory=Counter)
    _distinct_values: set[str] = field(default_factory=set)
    distinct_count_capped: bool = False

    def observe(self, value: RawScalar) -> None:
        if value is None or (isinstance(value, str) and not value.strip()):
            self.empty_count += 1
            return
        self.non_empty_count += 1
        self.value_kinds[_value_kind(value)] += 1
        if self.distinct_count_capped:
            return
        value_key = f"{type(value).__name__}:{value!r}"
        self._distinct_values.add(value_key)
        if len(self._distinct_values) > self.distinct_value_limit:
            self._distinct_values.clear()
            self.distinct_count_capped = True

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "empty_count": self.empty_count,
            "non_empty_count": self.non_empty_count,
            "distinct_count": (
                self.distinct_value_limit
                if self.distinct_count_capped
                else len(self._distinct_values)
            ),
            "distinct_count_capped": self.distinct_count_capped,
            "value_kinds": dict(sorted(self.value_kinds.items())),
        }


@dataclass
class SourceProfileAccumulator:
    source_name: str
    fields: dict[str, FieldProfile]
    row_count: int = 0

    def observe(self, values: dict[str, RawScalar]) -> None:
        self.row_count += 1
        for name, profile in self.fields.items():
            profile.observe(values[name])

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_name": self.source_name,
            "row_count": self.row_count,
            "field_count": len(self.fields),
            "field_profiles": [profile.as_dict() for profile in self.fields.values()],
        }


def _value_kind(value: RawScalar) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    return "string"


def transition_job(job: ImportJob, target: JobStatus) -> None:
    current = JobStatus(job.status)
    if target not in JOB_TRANSITIONS[current]:
        raise ImportContractError(
            "invalid_job_transition", f"Cannot move import job from {current} to {target}"
        )
    job.status = target


def transition_batch(batch: ImportBatch, target: BatchStatus) -> None:
    current = BatchStatus(batch.status)
    if target not in BATCH_TRANSITIONS[current]:
        raise ImportContractError(
            "invalid_batch_transition", f"Cannot move import batch from {current} to {target}"
        )
    batch.status = target


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
    transition_job(job, JobStatus.RUNNING)
    job.started_at = datetime.now(UTC)
    session.commit()
    return job


def _build_profiles(batch: ImportBatch) -> dict[str, SourceProfileAccumulator]:
    settings = get_settings()
    schemas = list(adapter_for(Path(batch.storage_path)).schemas())
    if not schemas:
        raise ImportContractError("source_empty", "Source contains no non-empty sheets")
    profiles: dict[str, SourceProfileAccumulator] = {}
    for schema in schemas:
        if len(schema.headers) > settings.max_fields_per_source:
            raise ImportContractError(
                "source_field_limit_exceeded",
                f"{schema.source_name} exceeds the {settings.max_fields_per_source}-field limit",
            )
        profiles[schema.source_name] = SourceProfileAccumulator(
            schema.source_name,
            {
                header: FieldProfile(header, settings.profile_distinct_value_limit)
                for header in schema.headers
            },
        )
    return profiles


def _load_import(session: Session, job: ImportJob, batch: ImportBatch) -> JobOutcome:
    transition_batch(batch, BatchStatus.LOADING)
    profiles = _build_profiles(batch)
    settings = get_settings()
    record_count = 0
    for record in adapter_for(Path(batch.storage_path)).records():
        profile = profiles.get(record.source_name)
        if profile is None:
            raise ImportContractError(
                "unexpected_source_name",
                f"Unexpected source name {record.source_name} while parsing batch",
            )
        if profile.row_count >= settings.max_rows_per_source:
            raise ImportContractError(
                "source_row_limit_exceeded",
                f"{record.source_name} exceeds the {settings.max_rows_per_source}-row limit",
            )
        profile.observe(dict(record.values))
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
        record_count += 1
        if record_count % 1_000 == 0:
            session.flush()
    for profile in profiles.values():
        summary = profile.as_dict()
        session.add(
            SourceProfile(
                import_batch_id=batch.id,
                source_name=profile.source_name,
                row_count=profile.row_count,
                field_count=len(profile.fields),
                field_profiles=summary["field_profiles"],
            )
        )
    transition_batch(batch, BatchStatus.AWAITING_MAPPING)
    batch.sheet_count = len(profiles)
    batch.original_row_count = record_count
    batch.pending_row_count = record_count
    batch.quarantined_row_count = 0
    batch.rejected_row_count = 0
    job.original_row_count = record_count
    job.pending_row_count = record_count
    job.accepted_row_count = 0
    job.quarantined_row_count = 0
    job.rejected_row_count = 0
    return JobOutcome(
        JobStatus.AWAITING_MAPPING,
        "Raw records profiled and loaded; source-to-canonical mapping awaits D0 approval",
    )


def process_job(session: Session, job: ImportJob) -> JobOutcome:
    if job.job_type == JobType.HEALTHCHECK:
        return JobOutcome(JobStatus.SUCCEEDED, "Worker healthcheck completed")
    batch = session.scalar(
        select(ImportBatch).where(ImportBatch.import_job_id == job.id).with_for_update()
    )
    if batch is None:
        return JobOutcome(JobStatus.FAILED, "Import batch is missing", "missing_batch")
    try:
        return _load_import(session, job, batch)
    except SourceAdapterError as error:
        session.rollback()
        return JobOutcome(JobStatus.FAILED, str(error), "source_parse_error")
    except ImportContractError as error:
        session.rollback()
        return JobOutcome(JobStatus.FAILED, str(error), error.code)


def record_outcome(session: Session, job: ImportJob, outcome: JobOutcome) -> None:
    managed_job = session.get(ImportJob, job.id)
    if managed_job is None:
        raise ImportContractError("missing_job", "Import job is missing")
    transition_job(managed_job, outcome.status)
    managed_job.completed_at = datetime.now(UTC)
    error_summary = (
        {"code": outcome.error_code, "reason": outcome.message}
        if outcome.status == JobStatus.FAILED
        else None
    )
    managed_job.error_summary = error_summary
    batch = session.scalar(select(ImportBatch).where(ImportBatch.import_job_id == managed_job.id))
    if batch is not None:
        if (
            outcome.status == JobStatus.AWAITING_MAPPING
            and batch.status != BatchStatus.AWAITING_MAPPING
        ):
            transition_batch(batch, BatchStatus.AWAITING_MAPPING)
        elif outcome.status == JobStatus.FAILED:
            transition_batch(batch, BatchStatus.FAILED)
            batch.error_summary = error_summary
            session.add(
                ImportValidationIssue(
                    import_batch_id=batch.id,
                    raw_source_row_id=None,
                    source_name=batch.source_filename,
                    original_row_number=None,
                    severity=ValidationSeverity.CRITICAL,
                    code=outcome.error_code or "worker_error",
                    field_name=None,
                    detail=outcome.message,
                    disposition=ValidationDisposition.REJECT,
                )
            )
    session.commit()
