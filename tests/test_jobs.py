from unittest.mock import Mock

import pytest
from b2b_domain.ingestion import ImportContractError
from b2b_domain.jobs import process_job, transition_batch, transition_job
from b2b_domain.models import BatchStatus, ImportBatch, ImportJob, JobStatus, JobType
from sqlalchemy.orm import Session

SHA256 = "0" * 64


def test_healthcheck_job_can_complete_without_an_import_contract() -> None:
    job = ImportJob(
        job_type=JobType.HEALTHCHECK,
        source_filename="worker-healthcheck",
        source_sha256=SHA256,
    )

    outcome = process_job(Mock(spec=Session), job)

    assert outcome.succeeded


def test_import_job_does_not_claim_success_before_d0_mapping() -> None:
    job = ImportJob(
        job_type=JobType.IMPORT,
        source_filename="private-source.csv",
        source_sha256=SHA256,
    )

    session = Mock(spec=Session)
    session.scalar.return_value = None

    outcome = process_job(session, job)

    assert not outcome.succeeded
    assert outcome.status == JobStatus.FAILED
    assert "batch is missing" in outcome.message


def test_state_machine_rejects_skipped_transitions() -> None:
    job = ImportJob(
        job_type=JobType.IMPORT,
        source_filename="source.csv",
        source_sha256=SHA256,
        status=JobStatus.QUEUED,
    )
    batch = ImportBatch(
        import_job_id=job.id,
        source_filename="source.csv",
        source_sha256=SHA256,
        storage_path="data/raw/imports/source.csv",
        status=BatchStatus.RECEIVED,
    )

    with pytest.raises(ImportContractError, match="Cannot move import job"):
        transition_job(job, JobStatus.AWAITING_MAPPING)
    with pytest.raises(ImportContractError, match="Cannot move import batch"):
        transition_batch(batch, BatchStatus.AWAITING_MAPPING)
