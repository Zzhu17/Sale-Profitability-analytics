import os
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from b2b_domain.models import ImportJob, JobStatus, RawSourceRow
from b2b_domain.settings import get_settings
from fastapi.testclient import TestClient
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

        assert run_once(session_factory)

        status_response = TestClient(app).get(f"/import-jobs/{job_id}")
        assert status_response.status_code == 200
        assert status_response.json()["status"] == JobStatus.AWAITING_MAPPING
        assert status_response.json()["pending_row_count"] == 2

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
