import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from sqlalchemy import select
from sqlalchemy.orm import Session

from b2b_domain.models import BatchStatus, ImportBatch, ImportJob, JobStatus, JobType
from b2b_domain.source_adapters import sha256_file

ALLOWED_SOURCE_SUFFIXES = frozenset({".csv", ".xlsx", ".xlsm"})


@dataclass(frozen=True)
class StagedSource:
    job_id: uuid.UUID
    original_filename: str
    path: Path
    sha256: str


def safe_filename(filename: str) -> str:
    basename = Path(filename).name
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "_", basename)
    if not cleaned or cleaned in {".", ".."}:
        raise ValueError("Source filename is invalid")
    if Path(cleaned).suffix.casefold() not in ALLOWED_SOURCE_SUFFIXES:
        raise ValueError("Source must be CSV, XLSX, or XLSM")
    return cleaned


def stage_source(
    source: BinaryIO,
    filename: str,
    raw_data_dir: Path,
    *,
    job_id: uuid.UUID | None = None,
) -> StagedSource:
    resolved_job_id = job_id or uuid.uuid4()
    original_filename = safe_filename(filename)
    job_dir = raw_data_dir / str(resolved_job_id)
    job_dir.mkdir(parents=True, exist_ok=False)
    target = job_dir / original_filename
    with target.open("xb") as destination:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            destination.write(chunk)
    return StagedSource(resolved_job_id, original_filename, target, sha256_file(target))


def create_import_job(session: Session, staged: StagedSource) -> tuple[ImportJob, ImportBatch]:
    existing = session.scalar(
        select(ImportJob).where(
            ImportJob.source_sha256 == staged.sha256,
            ImportJob.status.in_(
                [JobStatus.QUEUED, JobStatus.RUNNING, JobStatus.AWAITING_MAPPING]
            ),
        )
    )
    if existing is not None:
        raise ValueError(f"An active import already exists for SHA-256 {staged.sha256}")
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
    session.commit()
    return job, batch
