# Canonical promotion contract

S1-09 provides an internal promotion seam; it is not a public activation API.

Promotion requires both an approved mapping version and an immutable Gate 1 activation
backed by real anonymized evidence. Approval by itself is insufficient, so the synthetic
mapping-review flow cannot write canonical records.

For the selected batch and source, rows marked `quarantined` or `rejected` are excluded.
Rows still marked `pending` are pending mapping rather than silently invalid; after the
activated mapping applies successfully, the resulting canonical record is the accepted
mapped representation. Missing mapped fields fail the transaction instead of dropping a
row.

Each canonical record stores:

- the immutable raw source row identifier;
- the immutable mapping activation identifier, which identifies its mapping version;
- the canonical entity and mapped payload;
- the promotion timestamp.

Promotion is idempotent for each activation/raw-row pair. Empty values, unknown values,
and numeric or textual zero remain distinct in the canonical payload. Activation and
canonical records are append-only at the database layer.

Production activation remains unavailable until S1-08 audits real anonymized data and a
reviewer records the evidence hash and judgment.
