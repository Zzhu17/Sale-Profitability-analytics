# Gate 1 activation status

**Status: Blocked — no real anonymized data received.**

S1-08 cannot issue a real Pass, Conditional Pass, or Fail judgment until a private
anonymized delivery is audited. Synthetic evidence is limited to exercising the audit
code and cannot activate a source-to-canonical mapping.

## Synthetic rehearsal

Run on 2026-10-05 with:

```bash
uv run d0-audit \
  --template data/templates/Resume_Project_03_Sample_Data_Template.xlsx \
  --canonical-dir tests/fixtures/synthetic \
  --evidence-kind synthetic
```

The workbook template passed its structural check. The six fixture tables contained
3 customers, 2 products, 5 invoices, 5 invoice items, 1 return, and 5 inventory rows.
The intentionally adverse fixtures produced 7 critical, 7 warning, and 3 informational
findings. All five decision gates remained `Pending` because the evidence kind was
`synthetic`.

These counts validate the audit boundary only. They say nothing about real defect rates,
business performance, mapping fitness, purchase semantics, profitability, label windows,
eligibility, returns, inventory affinity, or modeling feasibility.

## Activation boundary

The engineering activation seam is ready and enforces all of the following:

- the mapping version is approved;
- the evidence kind is `real_anonymized`;
- the mapping judgment is `Pass` or `Conditional Pass`;
- a Conditional Pass includes a reviewer note;
- the reviewed evidence artifact has a recorded SHA-256;
- the activation record is attributable and append-only.

Until real data arrives, no mapping activation record can legitimately be created and no
canonical promotion can run. Follow the
[real anonymized data delivery checklist](data_audit/real_anonymized_data_delivery_checklist.md)
when a private extract becomes available.
