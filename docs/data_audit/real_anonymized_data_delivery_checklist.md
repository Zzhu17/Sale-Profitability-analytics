# Real anonymized data delivery checklist

Status: Ready for delivery; no real dataset received.

Place files only in the private `data/raw/` area (or an agreed private object store). Do not email source files into a public project, add them to Git, or copy them into synthetic fixtures.

## Before delivery

- [ ] Remove names, email addresses, phone numbers, street addresses, free-text notes, and other unnecessary PII.
- [ ] Replace customer, salesperson, product, invoice, and return identifiers with stable anonymous IDs; preserve joins across files.
- [ ] Keep original dates, statuses, unknowns, duplicates, negative/zero values, and source variation needed for the audit.
- [ ] Do not replace missing values with zero and do not manually normalize all source files into the template.
- [ ] Include complete extracts for the agreed date range, not only successful or active records.
- [ ] Include void, open, paid, returned, damaged/write-off, and no-stock records where available.
- [ ] Identify the source system/export report and export timestamp for each file.
- [ ] Provide the accounting profitability/COGS report needed to reconcile 20–30 sampled invoices.
- [ ] Document whether inventory snapshots are point-in-time or overwritten current state.
- [ ] Confirm the approved private transfer channel, retention period, and people permitted to access the data.

## Delivery manifest

Provide a manifest with these fields for every file:

```text
source_filename
source_system
report_or_export_name
exported_at
coverage_start
coverage_end
row_count
sha256
grain_description
timezone
currency
known_filters
known_limitations
```

## Minimum useful sources

- Invoices/orders with IDs, customer IDs, relevant dates, status, and totals.
- Invoice/order lines with stable line identity, product ID, quantity, price, discounts, and historical cost when available.
- Customer and product reference extracts.
- Returns/credits with original-invoice linkage when present and disposition when available.
- Dated inventory snapshots with product ID and on-hand/available quantity.
- Delivery/freight/handling and payment/credit-hold fields only when legitimately available.

Unknown availability is acceptable and must be stated; values must not be invented.
