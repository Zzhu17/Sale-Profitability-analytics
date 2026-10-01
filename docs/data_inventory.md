# D0 Data Inventory

**Status: Pending real anonymized data**

No private source extract has been received. The workbook in `data/templates/` is an audit/data-collection guide and is not evidence of source grain, coverage, relationships, or quality.

When data arrives, record each immutable file's SHA-256, source/export name, export time, coverage dates, row count, grain, timezone, currency, filters, and known limitations before transformation.

The import layer accepts CSV, XLSX, and XLSM as raw source containers. Excel sheets and CSV files become independent `source_name` values with their original row numbers. Source adapters preserve raw values; a separate reviewed mapping converts selected fields into the provisional canonical audit schema. The sample workbook is therefore not the only accepted production shape.
