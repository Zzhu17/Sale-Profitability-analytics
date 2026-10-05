import os
import uuid

import pytest
from b2b_domain.canonical import CanonicalEntity
from b2b_domain.d0 import EvidenceKind, GateJudgment
from b2b_domain.mapping_review import create_mapping_version, review_mapping_version
from b2b_domain.models import (
    BatchStatus,
    CanonicalRecord,
    ImportBatch,
    ImportJob,
    JobStatus,
    MappingActivation,
    MappingDecision,
    RawSourceRow,
    SourceProfile,
)
from b2b_domain.promotion import (
    PromotionError,
    activate_mapping_version,
    promote_mapping_version,
)
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")


@pytest.mark.integration
@pytest.mark.skipif(TEST_DATABASE_URL is None, reason="TEST_DATABASE_URL is not configured")
def test_promotion_requires_real_activation_and_retains_lineage() -> None:
    assert TEST_DATABASE_URL is not None
    engine = create_engine(TEST_DATABASE_URL)
    session_factory = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)
    source_sha256 = uuid.uuid4().hex * 2

    with session_factory() as session:
        job = ImportJob(
            job_type="import",
            status=JobStatus.AWAITING_MAPPING,
            source_filename="orders.csv",
            source_sha256=source_sha256,
        )
        session.add(job)
        session.flush()
        batch = ImportBatch(
            import_job_id=job.id,
            status=BatchStatus.AWAITING_MAPPING,
            source_filename="orders.csv",
            source_sha256=source_sha256,
            storage_path="data/raw/imports/orders.csv",
        )
        session.add(batch)
        session.flush()
        session.add(
            SourceProfile(
                import_batch_id=batch.id,
                source_name="orders",
                row_count=3,
                field_count=2,
                field_profiles=[{"name": "invoice_id"}, {"name": "amount"}],
            )
        )
        rows = [
            RawSourceRow(
                import_job_id=job.id,
                import_batch_id=batch.id,
                source_filename="orders.csv",
                source_sha256=source_sha256,
                source_name="orders",
                original_row_number=2,
                raw_payload={"invoice_id": "INV-1", "amount": ""},
                validation_status="pending",
                validation_errors=[],
            ),
            RawSourceRow(
                import_job_id=job.id,
                import_batch_id=batch.id,
                source_filename="orders.csv",
                source_sha256=source_sha256,
                source_name="orders",
                original_row_number=3,
                raw_payload={"invoice_id": "INV-2", "amount": "0"},
                validation_status="accepted",
                validation_errors=[],
            ),
            RawSourceRow(
                import_job_id=job.id,
                import_batch_id=batch.id,
                source_filename="orders.csv",
                source_sha256=source_sha256,
                source_name="orders",
                original_row_number=4,
                raw_payload={"invoice_id": "INV-3", "amount": "10"},
                validation_status="quarantined",
                validation_errors=[{"code": "review_required"}],
            ),
        ]
        session.add_all(rows)
        session.commit()

        mapping = create_mapping_version(
            session,
            import_batch_id=batch.id,
            source_name="orders",
            canonical_entity=CanonicalEntity.INVOICES,
            field_mappings={"invoice_id": "invoice_id", "amount": "gross_amount"},
            actor="analyst@example.com",
        )
        with pytest.raises(PromotionError, match="Only approved mappings") as draft_error:
            promote_mapping_version(session, mapping_version_id=mapping.id)
        assert draft_error.value.code == "mapping_not_approved"

        mapping = review_mapping_version(
            session,
            mapping_version_id=mapping.id,
            decision=MappingDecision.APPROVE,
            actor="reviewer@example.com",
        )
        with pytest.raises(PromotionError, match="Synthetic evidence") as synthetic_error:
            activate_mapping_version(
                session,
                mapping_version_id=mapping.id,
                evidence_kind=EvidenceKind.SYNTHETIC,
                judgment=GateJudgment.PASS,
                evidence_sha256="a" * 64,
                actor="gate-owner@example.com",
            )
        assert synthetic_error.value.code == "real_evidence_required"
        with pytest.raises(PromotionError, match="no real-data") as inactive_error:
            promote_mapping_version(session, mapping_version_id=mapping.id)
        assert inactive_error.value.code == "mapping_not_activated"
        with pytest.raises(PromotionError, match="review note") as conditional_error:
            activate_mapping_version(
                session,
                mapping_version_id=mapping.id,
                evidence_kind=EvidenceKind.REAL_ANONYMIZED,
                judgment=GateJudgment.CONDITIONAL_PASS,
                evidence_sha256="a" * 64,
                actor="gate-owner@example.com",
            )
        assert conditional_error.value.code == "conditional_note_required"

        activation = activate_mapping_version(
            session,
            mapping_version_id=mapping.id,
            evidence_kind=EvidenceKind.REAL_ANONYMIZED,
            judgment=GateJudgment.PASS,
            evidence_sha256="a" * 64,
            actor="gate-owner@example.com",
            note="Test-only state transition; not real business evidence",
        )
        first = promote_mapping_version(session, mapping_version_id=mapping.id)
        second = promote_mapping_version(session, mapping_version_id=mapping.id)

        assert first.created_count == 2
        assert first.existing_count == 0
        assert second.created_count == 0
        assert second.existing_count == 2
        canonical = list(
            session.scalars(
                select(CanonicalRecord)
                .where(CanonicalRecord.mapping_activation_id == activation.id)
                .order_by(CanonicalRecord.raw_source_row_id)
            )
        )
        assert [record.raw_source_row_id for record in canonical] == [rows[0].id, rows[1].id]
        assert canonical[0].canonical_payload["gross_amount"] == ""
        assert canonical[1].canonical_payload["gross_amount"] == "0"
        assert canonical[0].canonical_entity == CanonicalEntity.INVOICES
        stored_activation = session.scalar(
            select(MappingActivation).where(MappingActivation.id == activation.id)
        )
        assert stored_activation is not None
        assert stored_activation.mapping_version_id == mapping.id

    engine.dispose()
