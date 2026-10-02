from collections.abc import Mapping
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from b2b_domain.canonical import CanonicalEntity
from b2b_domain.models import (
    ImportBatch,
    MappingDecision,
    MappingReviewDecision,
    MappingVersion,
    MappingVersionStatus,
    SourceProfile,
)


class MappingReviewError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _actor(value: str) -> str:
    actor = value.strip()
    if not actor:
        raise MappingReviewError("invalid_actor", "Mapping actor is required")
    return actor


def _field_mappings(
    field_mappings: Mapping[str, str], source_profile: SourceProfile
) -> dict[str, str]:
    mappings = {source.strip(): target.strip() for source, target in field_mappings.items()}
    if not mappings or any(not source or not target for source, target in mappings.items()):
        raise MappingReviewError(
            "invalid_field_mappings", "Mappings must contain source and target fields"
        )
    if len(mappings.values()) != len(set(mappings.values())):
        raise MappingReviewError(
            "duplicate_canonical_field", "Canonical target fields must be unique per mapping"
        )
    source_fields = {profile["name"] for profile in source_profile.field_profiles}
    unknown_fields = sorted(set(mappings) - source_fields)
    if unknown_fields:
        raise MappingReviewError(
            "unknown_source_field",
            f"Mapping uses unknown source fields: {', '.join(unknown_fields)}",
        )
    return mappings


def create_mapping_version(
    session: Session,
    *,
    import_batch_id: object,
    source_name: str,
    canonical_entity: CanonicalEntity,
    field_mappings: Mapping[str, str],
    actor: str,
) -> MappingVersion:
    batch = session.get(ImportBatch, import_batch_id, with_for_update=True)
    if batch is None:
        raise MappingReviewError("missing_batch", "Import batch does not exist")
    source_profile = session.scalar(
        select(SourceProfile)
        .where(
            SourceProfile.import_batch_id == batch.id,
            SourceProfile.source_name == source_name,
        )
        .with_for_update()
    )
    if source_profile is None:
        raise MappingReviewError("missing_source_profile", "Source profile does not exist")
    mappings = _field_mappings(field_mappings, source_profile)
    latest_version = session.scalar(
        select(func.coalesce(func.max(MappingVersion.version), 0)).where(
            MappingVersion.import_batch_id == batch.id,
            MappingVersion.source_name == source_name,
        )
    )
    next_version = (latest_version or 0) + 1
    proposal = MappingVersion(
        import_batch_id=batch.id,
        source_name=source_name,
        version=next_version,
        canonical_entity=canonical_entity,
        field_mappings=mappings,
        status=MappingVersionStatus.DRAFT,
        created_by=_actor(actor),
    )
    session.add(proposal)
    session.commit()
    return proposal


def review_mapping_version(
    session: Session,
    *,
    mapping_version_id: object,
    decision: MappingDecision,
    actor: str,
    note: str | None = None,
) -> MappingVersion:
    proposal = session.get(MappingVersion, mapping_version_id, with_for_update=True)
    if proposal is None:
        raise MappingReviewError("missing_mapping_version", "Mapping version does not exist")
    if proposal.status != MappingVersionStatus.DRAFT:
        raise MappingReviewError(
            "mapping_not_draft", "Only draft mapping versions can be reviewed"
        )
    reviewer = _actor(actor)
    proposal.status = (
        MappingVersionStatus.APPROVED
        if decision == MappingDecision.APPROVE
        else MappingVersionStatus.REJECTED
    )
    proposal.reviewed_by = reviewer
    proposal.reviewed_at = datetime.now(UTC)
    proposal.review_note = note
    session.add(
        MappingReviewDecision(
            mapping_version_id=proposal.id,
            decision=decision,
            actor=reviewer,
            note=note,
        )
    )
    session.commit()
    return proposal
