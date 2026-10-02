import uuid
from collections.abc import Iterator
from typing import Annotated

from b2b_domain.canonical import CanonicalEntity
from b2b_domain.db import SessionLocal
from b2b_domain.ingestion import (
    ImportContractError,
    ImportRegistration,
    discard_staged_source,
    stage_source,
)
from b2b_domain.ingestion import (
    create_import_job as register_import_job,
)
from b2b_domain.mapping_review import (
    MappingReviewError,
    create_mapping_version,
    review_mapping_version,
)
from b2b_domain.models import (
    ImportBatch,
    ImportJob,
    ImportValidationIssue,
    MappingDecision,
    MappingReviewDecision,
    MappingVersion,
    SourceProfile,
)
from b2b_domain.settings import get_settings
from fastapi import Depends, FastAPI, File, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

app = FastAPI(
    title="B2B Sales Profitability Intelligence API",
    version="0.2.0",
    description="Gate 1 readiness; business contracts remain provisional pending real D0 data.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
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
    reused: bool


class ImportBatchResponse(BaseModel):
    id: uuid.UUID
    import_job_id: uuid.UUID
    status: str
    source_filename: str
    source_sha256: str
    sheet_count: int | None
    original_row_count: int | None
    pending_row_count: int | None
    quarantined_row_count: int | None
    rejected_row_count: int | None
    error_summary: dict[str, str] | None


class SourceProfileResponse(BaseModel):
    id: uuid.UUID
    source_name: str
    row_count: int
    field_count: int
    field_profiles: list[dict[str, object]]


class ValidationIssueResponse(BaseModel):
    id: int
    source_name: str
    original_row_number: int | None
    severity: str
    code: str
    field_name: str | None
    detail: str
    disposition: str


class MappingVersionResponse(BaseModel):
    id: uuid.UUID
    import_batch_id: uuid.UUID
    source_name: str
    version: int
    canonical_entity: str
    field_mappings: dict[str, str]
    status: str
    created_by: str
    reviewed_by: str | None
    review_note: str | None


class MappingVersionCreateRequest(BaseModel):
    source_name: str
    canonical_entity: CanonicalEntity
    field_mappings: dict[str, str]
    actor: str


class MappingReviewRequest(BaseModel):
    decision: MappingDecision
    actor: str
    note: str | None = None


class MappingReviewDecisionResponse(BaseModel):
    id: int
    mapping_version_id: uuid.UUID
    decision: str
    actor: str
    note: str | None


def get_session() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session


SessionDependency = Annotated[Session, Depends(get_session)]


def _response(registration: ImportRegistration) -> ImportJobResponse:
    job = registration.job
    batch = registration.batch
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
        reused=registration.reused,
    )


def _batch_response(batch: ImportBatch) -> ImportBatchResponse:
    return ImportBatchResponse(
        id=batch.id,
        import_job_id=batch.import_job_id,
        status=batch.status,
        source_filename=batch.source_filename,
        source_sha256=batch.source_sha256,
        sheet_count=batch.sheet_count,
        original_row_count=batch.original_row_count,
        pending_row_count=batch.pending_row_count,
        quarantined_row_count=batch.quarantined_row_count,
        rejected_row_count=batch.rejected_row_count,
        error_summary=batch.error_summary,
    )


def _mapping_response(mapping: MappingVersion) -> MappingVersionResponse:
    return MappingVersionResponse(
        id=mapping.id,
        import_batch_id=mapping.import_batch_id,
        source_name=mapping.source_name,
        version=mapping.version,
        canonical_entity=mapping.canonical_entity,
        field_mappings=mapping.field_mappings,
        status=mapping.status,
        created_by=mapping.created_by,
        reviewed_by=mapping.reviewed_by,
        review_note=mapping.review_note,
    )


def _mapping_error(error: MappingReviewError) -> HTTPException:
    return HTTPException(status_code=422, detail={"code": error.code, "message": str(error)})


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
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_filename", "message": "Source filename is required"},
        )
    staged = None
    try:
        settings = get_settings()
        staged = stage_source(
            source.file,
            source.filename,
            settings.raw_data_dir,
            max_upload_bytes=settings.max_upload_bytes,
        )
        registration = register_import_job(session, staged)
        if registration.reused:
            discard_staged_source(staged)
    except ImportContractError as error:
        if staged is not None:
            discard_staged_source(staged)
        raise HTTPException(
            status_code=422,
            detail={"code": error.code, "message": str(error)},
        ) from error
    except Exception:
        if staged is not None:
            discard_staged_source(staged)
        raise
    return _response(registration)


@app.get("/import-jobs/{job_id}", response_model=ImportJobResponse, tags=["imports"])
def get_import_job(job_id: uuid.UUID, session: SessionDependency) -> ImportJobResponse:
    job = session.get(ImportJob, job_id)
    batch = session.scalar(select(ImportBatch).where(ImportBatch.import_job_id == job_id))
    if job is None or batch is None:
        raise HTTPException(status_code=404, detail="Import job not found")
    return _response(ImportRegistration(job, batch, reused=False))


@app.get(
    "/import-jobs/{job_id}/batches",
    response_model=list[ImportBatchResponse],
    tags=["imports"],
)
def list_import_batches(job_id: uuid.UUID, session: SessionDependency) -> list[ImportBatchResponse]:
    if session.get(ImportJob, job_id) is None:
        raise HTTPException(status_code=404, detail="Import job not found")
    return [
        _batch_response(batch)
        for batch in session.scalars(
            select(ImportBatch)
            .where(ImportBatch.import_job_id == job_id)
            .order_by(ImportBatch.uploaded_at, ImportBatch.id)
        )
    ]


@app.get(
    "/import-batches/{batch_id}/source-profiles",
    response_model=list[SourceProfileResponse],
    tags=["imports"],
)
def list_source_profiles(
    batch_id: uuid.UUID, session: SessionDependency
) -> list[SourceProfileResponse]:
    if session.get(ImportBatch, batch_id) is None:
        raise HTTPException(status_code=404, detail="Import batch not found")
    return [
        SourceProfileResponse(
            id=profile.id,
            source_name=profile.source_name,
            row_count=profile.row_count,
            field_count=profile.field_count,
            field_profiles=profile.field_profiles,
        )
        for profile in session.scalars(
            select(SourceProfile)
            .where(SourceProfile.import_batch_id == batch_id)
            .order_by(SourceProfile.source_name)
        )
    ]


@app.get(
    "/import-batches/{batch_id}/validation-issues",
    response_model=list[ValidationIssueResponse],
    tags=["imports"],
)
def list_validation_issues(
    batch_id: uuid.UUID, session: SessionDependency
) -> list[ValidationIssueResponse]:
    if session.get(ImportBatch, batch_id) is None:
        raise HTTPException(status_code=404, detail="Import batch not found")
    return [
        ValidationIssueResponse(
            id=issue.id,
            source_name=issue.source_name,
            original_row_number=issue.original_row_number,
            severity=issue.severity,
            code=issue.code,
            field_name=issue.field_name,
            detail=issue.detail,
            disposition=issue.disposition,
        )
        for issue in session.scalars(
            select(ImportValidationIssue)
            .where(ImportValidationIssue.import_batch_id == batch_id)
            .order_by(ImportValidationIssue.id)
        )
    ]


@app.get(
    "/import-batches/{batch_id}/mapping-versions",
    response_model=list[MappingVersionResponse],
    tags=["mappings"],
)
def list_mapping_versions(
    batch_id: uuid.UUID, session: SessionDependency
) -> list[MappingVersionResponse]:
    if session.get(ImportBatch, batch_id) is None:
        raise HTTPException(status_code=404, detail="Import batch not found")
    return [
        _mapping_response(mapping)
        for mapping in session.scalars(
            select(MappingVersion)
            .where(MappingVersion.import_batch_id == batch_id)
            .order_by(MappingVersion.source_name, MappingVersion.version)
        )
    ]


@app.post(
    "/import-batches/{batch_id}/mapping-versions",
    response_model=MappingVersionResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["mappings"],
)
def create_mapping_proposal(
    batch_id: uuid.UUID,
    request: MappingVersionCreateRequest,
    session: SessionDependency,
) -> MappingVersionResponse:
    try:
        mapping = create_mapping_version(
            session,
            import_batch_id=batch_id,
            source_name=request.source_name,
            canonical_entity=request.canonical_entity,
            field_mappings=request.field_mappings,
            actor=request.actor,
        )
    except MappingReviewError as error:
        raise _mapping_error(error) from error
    return _mapping_response(mapping)


@app.post(
    "/mapping-versions/{mapping_version_id}/review-decisions",
    response_model=MappingVersionResponse,
    tags=["mappings"],
)
def create_mapping_review_decision(
    mapping_version_id: uuid.UUID,
    request: MappingReviewRequest,
    session: SessionDependency,
) -> MappingVersionResponse:
    try:
        mapping = review_mapping_version(
            session,
            mapping_version_id=mapping_version_id,
            decision=request.decision,
            actor=request.actor,
            note=request.note,
        )
    except MappingReviewError as error:
        raise _mapping_error(error) from error
    return _mapping_response(mapping)


@app.get(
    "/mapping-versions/{mapping_version_id}/review-decisions",
    response_model=list[MappingReviewDecisionResponse],
    tags=["mappings"],
)
def list_mapping_review_decisions(
    mapping_version_id: uuid.UUID, session: SessionDependency
) -> list[MappingReviewDecisionResponse]:
    if session.get(MappingVersion, mapping_version_id) is None:
        raise HTTPException(status_code=404, detail="Mapping version not found")
    return [
        MappingReviewDecisionResponse(
            id=decision.id,
            mapping_version_id=decision.mapping_version_id,
            decision=decision.decision,
            actor=decision.actor,
            note=decision.note,
        )
        for decision in session.scalars(
            select(MappingReviewDecision)
            .where(MappingReviewDecision.mapping_version_id == mapping_version_id)
            .order_by(MappingReviewDecision.id)
        )
    ]
