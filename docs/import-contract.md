# Import Contract v1

This contract covers Sprint 1 source intake through `awaiting_mapping`. It does not define a business mapping or promote rows into canonical tables.

## Accepted sources and limits

| Rule | Default | Environment setting |
|---|---:|---|
| Accepted file types | CSV, XLSX, XLSM | — |
| Maximum upload size | 100 MiB | `MAX_UPLOAD_BYTES` |
| Maximum rows per source/sheet | 250,000 | `MAX_ROWS_PER_SOURCE` |
| Maximum fields per source/sheet | 200 | `MAX_FIELDS_PER_SOURCE` |
| Exact distinct values retained per field profile | 10,000 | `PROFILE_DISTINCT_VALUE_LIMIT` |

Filenames are reduced to a safe basename before storage. Raw data is stored in the ignored `data/raw/imports/<job-id>/` path and must not be committed, logged, or used in public fixtures.

## Idempotency

The file SHA-256 is calculated while staging the source. Re-uploading content with the same SHA-256 while its import is `queued`, `running`, or `awaiting_mapping` returns the existing job and batch with `reused: true`; it does not create a second active batch. A failed import may be submitted again after the failure has been reviewed.

## State transitions

```text
Import job: queued → running → awaiting_mapping | succeeded | failed
Import batch: received → loading → awaiting_mapping | failed
```

Only a healthcheck job may reach `succeeded` in Sprint 1. An import batch remains `awaiting_mapping` until a reviewed source-to-canonical mapping exists.

## Validation and error taxonomy

| Code | Meaning | Result |
|---|---|---|
| `invalid_filename` | Filename is empty or unsafe after normalization | Request rejected |
| `unsupported_source` | File is not CSV, XLSX, or XLSM | Request rejected |
| `source_too_large` | Upload exceeds the configured byte limit | Request rejected; partial staged file removed |
| `source_empty` | Source contains no non-empty sheet/header | Batch failed; critical issue persisted |
| `source_parse_error` | CSV/XLSX/XLSM structure cannot be parsed | Batch failed; critical issue persisted |
| `source_field_limit_exceeded` | Source exceeds the configured field limit | Batch failed; critical issue persisted |
| `source_row_limit_exceeded` | Source exceeds the configured row limit | Batch failed; critical issue persisted |
| `unexpected_source_name` | Parsed rows do not match profiled source metadata | Batch failed; critical issue persisted |
| `worker_error` | Unexpected worker failure | Batch failed; critical issue persisted |

Every successfully parsed source records a source profile with row and field counts, empty/non-empty counts, value kinds, and bounded distinct counts. Profiles contain no sample values. Source rows remain append-only; validation issues are stored separately in `import_validation_issues`.

## Count invariant

For a batch that reaches `awaiting_mapping`:

```text
accepted_row_count + quarantined_row_count + rejected_row_count + pending_row_count
= original_row_count
```

Before mapping, all structurally parsed rows are `pending`. Canonical validation later assigns accepted, quarantined, or rejected dispositions without overwriting the raw row payload.
