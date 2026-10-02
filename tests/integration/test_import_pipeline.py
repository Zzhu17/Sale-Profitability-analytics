import os
import uuid
from collections.abc import Iterator
from io import BytesIO
from pathlib import Path

import pytest
from b2b_domain.models import (
    BatchStatus,
    ImportBatch,
    ImportJob,
    ImportValidationIssue,
    JobStatus,
    RawSourceRow,
    SourceProfile,
    ValidationDisposition,
    ValidationSeverity,
)
from b2b_domain.settings import get_settings
from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy import create_engine, select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session, sessionmaker

from services.api.main import app, get_session
from services.worker.main import run_once

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")


@pytest.mark.integration
@pytest.mark.skipif(TEST_DATABASE_URL is None, reason="TEST_DATABASE_URL is not configured")
def test_api_worker_and_immutable_lineage(tmp_path: Path) -> None:
    assert TEST_DATABASE_URL is not None
    engine = create_engine(TEST_DATABASE_URL)
    session_factory = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)

    def override_session() -> Iterator[Session]:
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    original_raw_dir = get_settings().raw_data_dir
    get_settings().raw_data_dir = tmp_path
    try:
        run_id = uuid.uuid4()
        source_bytes = f"id,amount,run\nA,,{run_id}\nB,0,{run_id}\n".encode()
        response = TestClient(app).post(
            "/import-jobs",
            files={"source": ("source.csv", source_bytes, "text/csv")},
        )
        assert response.status_code == 202
        job_id = response.json()["id"]
        assert response.json()["reused"] is False

        duplicate_response = TestClient(app).post(
            "/import-jobs",
            files={"source": ("source.csv", source_bytes, "text/csv")},
        )
        assert duplicate_response.status_code == 202
        assert duplicate_response.json()["id"] == job_id
        assert duplicate_response.json()["reused"] is True
        assert len(list(tmp_path.iterdir())) == 1

        assert run_once(session_factory)

        status_response = TestClient(app).get(f"/import-jobs/{job_id}")
        assert status_response.status_code == 200
        assert status_response.json()["status"] == JobStatus.AWAITING_MAPPING
        assert status_response.json()["pending_row_count"] == 2
        assert status_response.json()["reused"] is False

        with session_factory() as session:
            rows = list(
                session.scalars(
                    select(RawSourceRow)
                    .where(RawSourceRow.import_job_id == job_id)
                    .order_by(RawSourceRow.original_row_number)
                )
            )
            assert rows[0].raw_payload["amount"] == ""
            assert rows[1].raw_payload["amount"] == "0"
            assert rows[0].source_filename == "source.csv"
            assert rows[0].source_name == "source"
            assert rows[0].original_row_number == 2
            assert len(rows[0].source_sha256) == 64

            batch = session.scalar(select(ImportBatch).where(ImportBatch.import_job_id == job_id))
            assert batch is not None
            job = session.get(ImportJob, job_id)
            assert job is not None
            assert batch.status == BatchStatus.AWAITING_MAPPING
            assert batch.original_row_count == 2
            assert batch.pending_row_count == 2
            assert batch.quarantined_row_count == 0
            assert batch.rejected_row_count == 0
            assert (
                batch.pending_row_count
                + batch.quarantined_row_count
                + batch.rejected_row_count
                + (job.accepted_row_count or 0)
                == batch.original_row_count
            )

            profile = session.scalar(
                select(SourceProfile).where(SourceProfile.import_batch_id == batch.id)
            )
            assert profile is not None
            assert profile.source_name == "source"
            assert profile.row_count == 2
            assert profile.field_count == 3
            assert profile.field_profiles[1] == {
                "name": "amount",
                "empty_count": 1,
                "non_empty_count": 1,
                "distinct_count": 1,
                "distinct_count_capped": False,
                "value_kinds": {"string": 1},
            }
            assert session.scalars(
                select(ImportValidationIssue).where(
                    ImportValidationIssue.import_batch_id == batch.id
                )
            ).all() == []

            rows[0].validation_status = "accepted"
            with pytest.raises(DBAPIError, match="append-only"):
                session.commit()
            session.rollback()
            job = session.get(ImportJob, job_id)
            assert job is not None
            assert job.status == JobStatus.AWAITING_MAPPING
    finally:
        get_settings().raw_data_dir = original_raw_dir
        app.dependency_overrides.clear()
        engine.dispose()


@pytest.mark.integration
@pytest.mark.skipif(TEST_DATABASE_URL is None, reason="TEST_DATABASE_URL is not configured")
def test_excel_sheets_persist_separate_profiles(tmp_path: Path) -> None:
    assert TEST_DATABASE_URL is not None
    engine = create_engine(TEST_DATABASE_URL)
    session_factory = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)

    def override_session() -> Iterator[Session]:
        with session_factory() as session:
            yield session

    workbook = Workbook()
    orders = workbook.active
    orders.title = "Orders"
    orders.append(["invoice_id", "amount"])
    orders.append([str(uuid.uuid4()), 10])
    returns = workbook.create_sheet("Returns")
    returns.append(["return_id", "reason"])
    returns.append(["RET-1", "damaged"])
    payload = BytesIO()
    workbook.save(payload)

    app.dependency_overrides[get_session] = override_session
    original_raw_dir = get_settings().raw_data_dir
    get_settings().raw_data_dir = tmp_path
    try:
        response = TestClient(app).post(
            "/import-jobs",
            files={
                "source": (
                    "multi-sheet.xlsx",
                    payload.getvalue(),
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
        )
        assert response.status_code == 202
        job_id = response.json()["id"]

        assert run_once(session_factory)

        with session_factory() as session:
            batch = session.scalar(select(ImportBatch).where(ImportBatch.import_job_id == job_id))
            assert batch is not None
            assert batch.status == BatchStatus.AWAITING_MAPPING
            assert batch.sheet_count == 2
            assert batch.original_row_count == 2
            profiles = {
                profile.source_name: profile
                for profile in session.scalars(
                    select(SourceProfile).where(SourceProfile.import_batch_id == batch.id)
                )
            }
            assert set(profiles) == {"Orders", "Returns"}
            assert profiles["Orders"].row_count == 1
            assert profiles["Orders"].field_profiles[1]["value_kinds"] == {"number": 1}
            assert profiles["Returns"].row_count == 1
            assert profiles["Returns"].field_profiles[1]["distinct_count"] == 1
    finally:
        get_settings().raw_data_dir = original_raw_dir
        app.dependency_overrides.clear()
        engine.dispose()


@pytest.mark.integration
@pytest.mark.skipif(TEST_DATABASE_URL is None, reason="TEST_DATABASE_URL is not configured")
def test_parse_failure_persists_a_critical_issue(tmp_path: Path) -> None:
    assert TEST_DATABASE_URL is not None
    engine = create_engine(TEST_DATABASE_URL)
    session_factory = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)

    def override_session() -> Iterator[Session]:
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    original_raw_dir = get_settings().raw_data_dir
    get_settings().raw_data_dir = tmp_path
    try:
        run_id = uuid.uuid4()
        source_bytes = f"id,amount,run\nA,{run_id}\n".encode()
        response = TestClient(app).post(
            "/import-jobs",
            files={"source": ("broken.csv", source_bytes, "text/csv")},
        )
        assert response.status_code == 202
        job_id = response.json()["id"]

        assert run_once(session_factory)

        with session_factory() as session:
            job = session.get(ImportJob, job_id)
            assert job is not None
            assert job.status == JobStatus.FAILED
            assert job.error_summary == {
                "code": "source_parse_error",
                "reason": "broken.csv:2: expected 3 fields, found 2",
            }
            batch = session.scalar(select(ImportBatch).where(ImportBatch.import_job_id == job_id))
            assert batch is not None
            assert batch.status == BatchStatus.FAILED
            issue = session.scalar(
                select(ImportValidationIssue).where(
                    ImportValidationIssue.import_batch_id == batch.id
                )
            )
            assert issue is not None
            assert issue.code == "source_parse_error"
            assert issue.severity == ValidationSeverity.CRITICAL
            assert issue.disposition == ValidationDisposition.REJECT
            assert session.scalars(
                select(RawSourceRow).where(RawSourceRow.import_batch_id == batch.id)
            ).all() == []
    finally:
        get_settings().raw_data_dir = original_raw_dir
        app.dependency_overrides.clear()
        engine.dispose()
