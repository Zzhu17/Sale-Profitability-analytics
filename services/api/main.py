import uuid
from collections.abc import Iterator
from typing import Annotated

from b2b_domain.db import SessionLocal
from b2b_domain.ingestion import create_import_job as register_import_job
from b2b_domain.ingestion import stage_source
from b2b_domain.models import ImportBatch, ImportJob
from b2b_domain.settings import get_settings
from fastapi import Depends, FastAPI, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

app = FastAPI(
    title="B2B Sales Profitability Intelligence API",
    version="0.2.0",
    description="Gate 1 readiness; business contracts remain provisional pending real D0 data.",
)


class ImportJobResponse(BaseModel):
    id: uuid.UUID
    batch_id: uuid.UUID
    status: str
    source_filename: str
    source_sha256: str
    original_row_count: int | None
    pending_row_count: int | None
    quarantined_row_count: int | None
    rejected_row_count: int | None


def get_session() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session


SessionDependency = Annotated[Session, Depends(get_session)]


def _response(job: ImportJob, batch: ImportBatch) -> ImportJobResponse:
    return ImportJobResponse(
        id=job.id,
        batch_id=batch.id,
        status=job.status,
        source_filename=job.source_filename,
        source_sha256=job.source_sha256,
        original_row_count=job.original_row_count,
        pending_row_count=job.pending_row_count,
        quarantined_row_count=job.quarantined_row_count,
        rejected_row_count=job.rejected_row_count,
    )


@app.get("/healthz", tags=["system"])
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post(
    "/import-jobs",
    response_model=ImportJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["imports"],
)
def create_import_job(
    source: Annotated[UploadFile, File(description="CSV, XLSX, or XLSM source export")],
    session: SessionDependency,
) -> ImportJobResponse:
    if not source.filename:
        raise HTTPException(status_code=422, detail="Source filename is required")
    try:
        staged = stage_source(source.file, source.filename, get_settings().raw_data_dir)
        job, batch = register_import_job(session, staged)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return _response(job, batch)


@app.get("/import-jobs/{job_id}", response_model=ImportJobResponse, tags=["imports"])
def get_import_job(job_id: uuid.UUID, session: SessionDependency) -> ImportJobResponse:
    job = session.get(ImportJob, job_id)
    batch = session.scalar(select(ImportBatch).where(ImportBatch.import_job_id == job_id))
    if job is None or batch is None:
        raise HTTPException(status_code=404, detail="Import job not found")
    return _response(job, batch)
