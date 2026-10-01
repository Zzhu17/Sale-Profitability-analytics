# D0 Data Quality Report

**Status: Pending real anonymized data**

The audit framework is runnable against synthetic boundary fixtures and validates the workbook guide structure. It has not inspected real business data, so it contains no real row counts, defect rates, distributions, pass/fail claims, or modeling conclusions. The machine-readable skeleton is `docs/data_audit/d0_summary.json`.

Implemented readiness checks:

- table grain, required keys, duplicates, and foreign-key coverage;
- date and decimal parseability, future dates, and positive-quantity rules;
- deterministic entity normalization and fuzzy candidate generation for human review;
- invoice-row distribution, status cross-tab, and retained Void-line visibility;
- missing, zero/nonpositive, and positive historical cost coverage plus COGS reconciliation;
- exact/unallocated return evidence without fabricated links;
- complete product-by-date inventory coverage where a zero snapshot remains observed;
- candidate 14/30/60/90-day observable timeline boundaries without selecting a label;
- explicit row dispositions: Critical → reject, Warning → quarantine, Informational → flag.

## Decision gates

| Capability | Judgment | Evidence required |
|---|---|---|
| Customer 360 | Pending | Grain, keys, entity mapping coverage, date/status semantics |
| Profitability analytics | Pending | Historical cost coverage and 20–30 invoice reconciliation |
| Reorder-cycle rules | Pending | Valid purchase events and observed gap distributions |
| Purchase-propensity ML | Pending | Label volume, temporal coverage, feature availability |
| Temporal backtesting | Pending | Fully observable expanding-window folds and final test window |

Critical, warning, and informational severities will be reported separately. Long-tail B2B values will be reviewed with IQR, MAD, and percentiles rather than automatically deleted.
