import string
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from b2b_domain.d0 import EvidenceKind, GateJudgment
from b2b_domain.models import (
    CanonicalRecord,
    MappingActivation,
    MappingVersion,
    MappingVersionStatus,
    RawSourceRow,
)


class PromotionError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class PromotionResult:
    mapping_activation_id: uuid.UUID
    created_count: int
    existing_count: int


def _actor(value: str) -> str:
    actor = value.strip()
    if not actor:
        raise PromotionError("invalid_actor", "Activation actor is required")
    return actor


def _sha256(value: str) -> str:
    digest = value.strip().lower()
    if len(digest) != 64 or any(character not in string.hexdigits for character in digest):
        raise PromotionError(
            "invalid_evidence_sha256",
            "Evidence SHA-256 must be 64 hex characters",
        )
    return digest


def activate_mapping_version(
    session: Session,
    *,
    mapping_version_id: object,
    evidence_kind: EvidenceKind,
    judgment: GateJudgment,
    evidence_sha256: str,
    actor: str,
    note: str | None = None,
) -> MappingActivation:
    mapping = session.get(MappingVersion, mapping_version_id, with_for_update=True)
    if mapping is None:
        raise PromotionError("missing_mapping_version", "Mapping version does not exist")
    if mapping.status != MappingVersionStatus.APPROVED:
        raise PromotionError("mapping_not_approved", "Only approved mappings can be activated")
    if evidence_kind != EvidenceKind.REAL_ANONYMIZED:
        raise PromotionError(
            "real_evidence_required",
            "Synthetic evidence cannot activate canonical promotion",
        )
    if judgment not in {GateJudgment.PASS, GateJudgment.CONDITIONAL_PASS}:
        raise PromotionError(
            "gate_not_passed",
            "Mapping activation requires Pass or Conditional Pass",
        )
    activation_note = note.strip() if note else None
    if judgment == GateJudgment.CONDITIONAL_PASS and not activation_note:
        raise PromotionError(
            "conditional_note_required",
            "Conditional Pass activation requires a review note",
        )
    existing = session.scalar(
        select(MappingActivation).where(
            MappingActivation.mapping_version_id == mapping.id
        )
    )
    if existing is not None:
        return existing
    activation = MappingActivation(
        mapping_version_id=mapping.id,
        evidence_kind=evidence_kind,
        judgment=judgment,
        evidence_sha256=_sha256(evidence_sha256),
        activated_by=_actor(actor),
        note=activation_note,
    )
    session.add(activation)
    session.commit()
    return activation


def promote_mapping_version(
    session: Session,
    *,
    mapping_version_id: object,
) -> PromotionResult:
    mapping = session.get(MappingVersion, mapping_version_id)
    if mapping is None:
        raise PromotionError("missing_mapping_version", "Mapping version does not exist")
    if mapping.status != MappingVersionStatus.APPROVED:
        raise PromotionError("mapping_not_approved", "Only approved mappings can promote rows")
    activation = session.scalar(
        select(MappingActivation)
        .where(MappingActivation.mapping_version_id == mapping.id)
        .with_for_update()
    )
    if activation is None:
        raise PromotionError(
            "mapping_not_activated",
            "Approved mapping has no real-data Gate 1 activation",
        )
    rows = list(
        session.scalars(
            select(RawSourceRow)
            .where(
                RawSourceRow.import_batch_id == mapping.import_batch_id,
                RawSourceRow.source_name == mapping.source_name,
                RawSourceRow.validation_status.notin_(("quarantined", "rejected")),
            )
            .order_by(RawSourceRow.id)
        )
    )
    existing_ids = set(
        session.scalars(
            select(CanonicalRecord.raw_source_row_id).where(
                CanonicalRecord.mapping_activation_id == activation.id
            )
        )
    )
    created_count = 0
    for row in rows:
        if row.id in existing_ids:
            continue
        missing = sorted(set(mapping.field_mappings) - set(row.raw_payload))
        if missing:
            raise PromotionError(
                "mapping_source_field_missing",
                f"Raw row {row.original_row_number} is missing mapped fields: {', '.join(missing)}",
            )
        session.add(
            CanonicalRecord(
                mapping_activation_id=activation.id,
                raw_source_row_id=row.id,
                canonical_entity=mapping.canonical_entity,
                canonical_payload={
                    target: row.raw_payload[source]
                    for source, target in mapping.field_mappings.items()
                },
            )
        )
        created_count += 1
    session.commit()
    return PromotionResult(activation.id, created_count, len(existing_ids))
