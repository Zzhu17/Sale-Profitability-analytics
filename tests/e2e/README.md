# End-to-end tests

The Sprint 1 synthetic browser path uploads an in-memory derivative of `invoices.csv`, waits for `awaiting_mapping`, inspects the field profile, creates a mapping draft, and approves it. It uses only repository fixtures and does not require D0 or private data.

Run it against the local Compose stack with `pnpm test:e2e`. GitHub Actions starts the same stack, installs Chromium, runs this flow, and uploads Playwright traces, screenshots, videos, and Compose logs when it fails.
