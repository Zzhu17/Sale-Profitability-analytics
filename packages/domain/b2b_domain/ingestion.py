import hashlib
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from b2b_domain.models import BatchStatus, ImportBatch, ImportJob, JobStatus, JobType

ALLOWED_SOURCE_SUFFIXES = frozenset({".csv", ".xlsx", ".xlsm"})
DEFAULT_MAX_UPLOAD_BYTES = 100 * 1024 * 1024
ACTIVE_IMPORT_STATUSES = frozenset(
    {JobStatus.QUEUED, JobStatus.RUNNING, JobStatus.AWAITING_MAPPING}
)


class ImportContractError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class StagedSource:
    job_id: uuid.UUID
    original_filename: str
    path: Path
    sha256: str


@dataclass(frozen=True)
class ImportRegistration:
    job: ImportJob
    batch: ImportBatch
    reused: bool


def safe_filename(filename: str) -> str:
    basename = Path(filename).name
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "_", basename)
    if not cleaned or cleaned in {".", ".."}:
        raise ImportContractError("invalid_filename", "Source filename is invalid")
    if Path(cleaned).suffix.casefold() not in ALLOWED_SOURCE_SUFFIXES:
        raise ImportContractError("unsupported_source", "Source must be CSV, XLSX, or XLSM")
    return cleaned


def stage_source(
    source: BinaryIO,
    filename: str,
    raw_data_dir: Path,
    *,
    job_id: uuid.UUID | None = None,
    max_upload_bytes: int = DEFAULT_MAX_UPLOAD_BYTES,
) -> StagedSource:
    if max_upload_bytes <= 0:
        raise ImportContractError("invalid_upload_limit", "Upload limit must be positive")
    resolved_job_id = job_id or uuid.uuid4()
    original_filename = safe_filename(filename)
    job_dir = raw_data_dir / str(resolved_job_id)
    target = job_dir / original_filename
    digest = hashlib.sha256()
    uploaded_bytes = 0
    created_job_dir = False
    try:
        job_dir.mkdir(parents=True, exist_ok=False)
        created_job_dir = True
        with target.open("xb") as destination:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                uploaded_bytes += len(chunk)
                if uploaded_bytes > max_upload_bytes:
                    raise ImportContractError(
                        "source_too_large",
                        f"Source exceeds the {max_upload_bytes}-byte upload limit",
                    )
                digest.update(chunk)
                destination.write(chunk)
    except Exception:
        if created_job_dir:
            target.unlink(missing_ok=True)
            job_dir.rmdir()
        raise
    return StagedSource(resolved_job_id, original_filename, target, digest.hexdigest())


def discard_staged_source(staged: StagedSource) -> None:
    staged.path.unlink(missing_ok=True)
    staged.path.parent.rmdir()


def _active_import(session: Session, source_sha256: str) -> tuple[ImportJob, ImportBatch] | None:
    job = session.scalar(
        select(ImportJob)
        .where(
            ImportJob.source_sha256 == source_sha256,
            ImportJob.status.in_(ACTIVE_IMPORT_STATUSES),
        )
        .order_by(ImportJob.uploaded_at, ImportJob.id)
    )
    if job is None:
        return None
    batch = session.scalar(
        select(ImportBatch)
        .where(ImportBatch.import_job_id == job.id)
        .order_by(ImportBatch.uploaded_at, ImportBatch.id)
    )
    if batch is None:
        raise ImportContractError("missing_batch", "Active import is missing its batch")
    return job, batch


def create_import_job(session: Session, staged: StagedSource) -> ImportRegistration:
    existing = _active_import(session, staged.sha256)
    if existing is not None:
        job, batch = existing
        return ImportRegistration(job, batch, reused=True)
    job = ImportJob(
        id=staged.job_id,
        job_type=JobType.IMPORT,
        status=JobStatus.QUEUED,
        source_filename=staged.original_filename,
        source_sha256=staged.sha256,
    )
    batch = ImportBatch(
        import_job_id=job.id,
        status=BatchStatus.RECEIVED,
        source_filename=staged.original_filename,
        source_sha256=staged.sha256,
        storage_path=str(staged.path),
    )
    session.add(job)
    session.flush()
    session.add(batch)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        existing = _active_import(session, staged.sha256)
        if existing is None:
            raise
        active_job, active_batch = existing
        return ImportRegistration(active_job, active_batch, reused=True)
    return ImportRegistration(job, batch, reused=False)
