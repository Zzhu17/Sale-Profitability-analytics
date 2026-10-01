# Entity Resolution Rules

**Status: Provisional — pending real anonymized data**

Locked direction:

1. Preserve the original value.
2. Apply deterministic trimming, repeated-space collapse, case/punctuation normalization, and approved abbreviation rules.
3. Generate fuzzy candidates only after deterministic matching, using available auxiliary fields.
4. Require human confirmation for high-risk or ambiguous matches.

Mappings retain `internal_id`, `canonical_name`, `original_name`, `match_method`, `match_confidence`, and `review_status`. Thresholds and approved abbreviations are not frozen.

`data/mappings/source_mappings.example.json` illustrates the separation between a raw source name and canonical fields. It is an example only and is not an approved mapping contract.
