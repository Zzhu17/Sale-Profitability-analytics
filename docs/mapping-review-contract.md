# Mapping Review Contract v1

This contract governs Sprint 1 mapping proposals only. It records how source fields could map to the provisional canonical entities; it does not promote rows into canonical tables or freeze a real-data mapping before Gate 1.

## Proposal versions

- A proposal belongs to one import batch and one profiled source/sheet.
- A new proposal receives the next positive version number for that batch and source.
- Each proposal records its creator and creation time, canonical entity, and source-to-target field mapping.
- Mapped source fields must exist in the stored source profile. Canonical target fields cannot be duplicated inside a proposal.

## Review decisions

Only a `draft` proposal can receive a review decision. A decision is either `approve` or `reject` and records its actor, timestamp, and optional note. The proposal retains its resulting `approved` or `rejected` status and reviewer metadata; the decision is also stored as an append-only audit record.

An approved proposal is immutable at the database layer. A changed mapping must be submitted as a new version. Rejected proposals also remain as audit evidence and do not authorize canonical promotion.

## Gate boundary

An approved synthetic proposal supports only the Sprint 1 review workflow. Gate 1 must still audit real anonymized source data and approve the actual source-to-canonical contracts before any canonical promotion is enabled.
