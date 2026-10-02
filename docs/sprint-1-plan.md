# Sprint 1 Plan — Import, Validation, and Mapping Review

- **Planning status:** In progress — S1-01 through S1-03 complete
- **Implementation gate:** Generic engineering work may begin; real source activation remains blocked until Gate 1.
- **Capacity assumption:** One developer, ordered backlog, no calendar commitment until capacity is confirmed.

## Outcome

Deliver one auditable vertical slice from source upload to a reviewed mapping decision:

```text
Upload CSV/XLSX/XLSM
→ preserve immutable raw lineage
→ parse and validate source rows
→ expose issues and source-field profiles
→ review a versioned source-to-canonical mapping
→ stop before canonical promotion unless the mapping is approved
```

Sprint 1 does not freeze business definitions from synthetic fixtures. When real anonymized data arrives, Gate 1 runs in parallel and supplies the approved mapping and contracts needed to activate canonical promotion.

## Scope

### Must have

- Production-shaped import validation and explicit job/batch state transitions.
- Source and sheet-level row counts, field profiles, and structured validation issues.
- Versioned mapping proposals and reviewer decisions with an audit trail.
- API endpoints for batch status, validation results, and mapping review.
- Minimal web workflow for upload, polling, validation review, and mapping decisions.
- Integration and browser-level coverage for the synthetic vertical slice.
- No private source data in Git, logs, fixtures, images, or public deployments.

### Gate 1 activation work

- Inventory and hash every real anonymized source extract.
- Run D0 and issue separate Pass / Conditional Pass / Fail judgments.
- Freeze source-to-canonical mappings and the contracts required by downstream work.
- Exercise approved mappings against real anonymized samples without committing those samples.

### Out of scope

- Final profitability calculations or margin claims.
- Overdue, reactivation, or high-profit recommendation queues.
- Inventory-affinity thresholds and eligibility rules.
- Customer 360, action/outcome logging, and admin analytics.
- Training data generation, model training, model metrics, or business-impact claims.

These remain Sprint 2+ candidates after Gate 1 evidence is available.

## Technical guardrails

- Raw source rows remain append-only and retain file hash, batch, source/sheet, and original row number.
- Mapping approval is explicit. An unapproved mapping cannot create canonical records.
- Approved mapping versions are immutable; changes create a new version.
- Canonical rows must retain links to the raw row and mapping version that produced them.
- Unknown, empty, zero, rejected, and quarantined values remain distinct.
- Validation output uses stable machine-readable codes plus reviewer-facing explanations.
- Raw payloads and customer identifiers must not be written to application logs.
- Synthetic fixtures test behavior only and never support real-business conclusions.

## Ordered backlog

| ID | Work package | Size | Dependency | Acceptance criteria |
|---|---|---:|---|---|
| S1-01 | Import contract and state machine | S | None | Complete — allowed files, limits, idempotency behavior, error taxonomy, and job/batch transitions are documented and tested. |
| S1-02 | Source profiling and validation persistence | M | S1-01 | Complete — CSV sheets/files produce row counts, field profiles, and structured issues without mutating raw rows. |
| S1-03 | Worker validation flow | M | S1-02 | Complete — worker moves a batch deterministically from received through loading to awaiting mapping or failed; counts reconcile to source rows. |
| S1-04 | Mapping version and review persistence | M | S1-01 | Complete — draft, approved, and rejected decisions are attributable; approved versions cannot be edited in place. |
| S1-05 | Import and mapping-review API | M | S1-03, S1-04 | Complete — API lists batches, source profiles, issues, mapping proposals, and review decisions with stable response models. |
| S1-06 | Minimal web vertical slice | M | S1-05 | Complete — user can upload, poll status, inspect issues, and approve or reject a mapping proposal with accessible loading/error states. |
| S1-07 | Integration and E2E coverage | M | S1-03–S1-06 | PostgreSQL integration tests and one synthetic browser flow pass in CI; private data is not required. |
| S1-08 | Gate 1 real-data audit and mapping activation | M | Real anonymized data | D0 outputs are evidence-backed; approved mapping is exercised against private data; unresolved gates are explicit. |
| S1-09 | Canonical promotion seam | L | S1-08 | Approved mappings can promote accepted rows with raw-row and mapping-version lineage; unapproved mappings cannot. |

`S1-09` is a stretch item. If Gate 1 arrives late, Sprint 1 ends with the reviewed mapping workflow and canonical promotion moves to the next sprint.

## Execution order

1. **Contract:** S1-01 defines states, errors, and idempotency before schema or API expansion.
2. **Backend vertical slice:** S1-02 through S1-05 produce inspectable validation and review behavior.
3. **User workflow:** S1-06 exposes only the decisions supported by the backend.
4. **Quality:** S1-07 makes the complete synthetic path repeatable in CI.
5. **Activation:** S1-08 freezes real mappings and contracts; S1-09 consumes only approved evidence.

## Sprint acceptance criteria

- Uploading a supported file returns a traceable job and batch identifier.
- Re-upload behavior is deterministic and covered by tests.
- Every parsed row retains immutable source lineage.
- Batch counts reconcile: accepted + quarantined + rejected + pending equals original rows.
- Critical issues reject, warnings quarantine, and informational issues flag without silently dropping rows.
- A reviewer can inspect source fields, samples, and issues before recording a mapping decision.
- Mapping decisions record actor, timestamp, status, and version.
- Unapproved mappings cannot promote data into canonical tables.
- Synthetic integration and UI flows pass in GitHub Actions.
- Real anonymized data remains outside Git and public artifacts.

## Gate 1 inputs required

Real anonymized delivery may contain multiple CSV files or workbook sheets. It must include enough history and fields to evaluate customer/product identity, invoice and line grain, status/date semantics, historical costs, discounts/tax treatment, returns, and inventory coverage. The delivery checklist remains the source of truth:

- [`docs/data_audit/real_anonymized_data_delivery_checklist.md`](data_audit/real_anonymized_data_delivery_checklist.md)

## Risks and controls

| Risk | Control |
|---|---|
| Real source shape differs from the sample workbook | Keep adapters source-oriented and mappings reviewed/versioned; do not hard-code workbook names as the production contract. |
| Mapping UI encodes provisional business rules | Limit Sprint 1 to source fields, canonical candidates, validation evidence, and explicit reviewer decisions. |
| Raw data leaks through logs or fixtures | Log identifiers and counts, not payloads; keep `data/raw/` ignored; use synthetic E2E fixtures. |
| Retry creates duplicate rows | Define hash/batch idempotency in S1-01 and enforce lineage uniqueness in PostgreSQL. |
| Sprint expands into downstream analytics | Hold profitability, recommendations, Customer 360, and ML behind Gate 1 and later sprint plans. |

## Definition of done

- Code, migrations, API schemas, UI states, and documentation agree on the workflow.
- Migration upgrade and downgrade paths are tested.
- Ruff, mypy, pytest, ESLint, Vitest, frontend build, Compose build, integration tests, and the selected E2E flow pass in CI.
- Security and privacy boundaries are verified with synthetic fixtures.
- Any item blocked by missing real evidence is marked blocked rather than replaced by a synthetic conclusion.
