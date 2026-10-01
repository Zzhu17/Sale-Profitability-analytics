# ADR 0002: PostgreSQL-backed jobs

- Status: Accepted (Locked direction)
- Date: 2026-10-01

## Decision

Store batch work in `import_jobs`. Workers claim the oldest queued job with `FOR UPDATE SKIP LOCKED`, transition it to `running`, and persist a terminal outcome. Raw source rows retain file hash, upload batch, original row number, raw payload, validation state, and error reason.

`raw_source_rows` is append-only: the initial migration rejects `UPDATE` and `DELETE` at the database layer.

## Consequences

- No Redis or Celery dependency is required for the MVP.
- Failed jobs retain an auditable reason.
- Import jobs cannot succeed until a source adapter is approved from D0 evidence; the Sprint 0 worker reports that condition explicitly.
