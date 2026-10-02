# End-to-end tests

The Sprint 1 synthetic browser path has been verified against local Compose services: upload `customers.csv`, wait for `awaiting_mapping`, inspect the field profile, create a mapping draft, and approve it. It uses only repository fixtures and does not require D0 or private data.

GitHub Actions currently runs the PostgreSQL integration suite and frontend unit tests. A browser automation job remains the next S1-07 task before this manual flow can be described as CI coverage.
