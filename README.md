# B2B Sales Profitability Intelligence

Sprint 0 foundation for a decision-support product that helps B2B sales teams identify **accounts warranting review**. This repository is a production-shaped modular monolith; it is not yet a finished recommendation product.

Sprint 0 engineering and the Sprint 1 synthetic vertical slice are complete. The [Sprint 1 plan](docs/sprint-1-plan.md) records S1-08 as blocked on real anonymized data; the S1-09 canonical promotion seam is implemented but remains inactive behind that gate.

## Current boundary

- **Locked:** product purpose, hypotheses, MVP boundary, modular-monolith direction, PostgreSQL job queue, and public/private data separation. See the [development handoff](docs/Resume_Project_03_Codex_Handoff.md).
- **Provisional:** canonical source mapping, purchase event, profitability formula, label horizon, eligibility thresholds, return attribution, inventory affinity, and ML feasibility. These remain pending until D0 audits real anonymized data.
- **Not done in Sprint 0:** final model training, final dashboard, model metrics, business outcomes, or causal-impact claims.

Synthetic data is permitted only for public demos, automated tests, edge cases, and pipeline checks. Real anonymized data stays private under `data/raw/` and must never enter public images, fixtures, artifacts, or deployments. Synthetic results are never evidence of real-world performance.

## Repository map

```text
apps/web/                 React + TypeScript + Vite shell
services/api/             FastAPI service
services/worker/          PostgreSQL-backed job worker
packages/domain/          Shared database and D0 audit logic
analytics/dbt/            Reserved for evidence-backed transforms
ml/                       Reserved until the modeling gate
data/templates/           Audit/data-collection template
data/raw/                 Private immutable source drops (ignored)
data/synthetic/           Public demo-only data
docs/                     Handoff, ADRs, D0 pending outputs
migrations/               Alembic schema migrations
tests/                    Python, integration, and future E2E tests
```

## Toolchain

- Node.js `22` and pnpm `11`
- Python `3.12` managed with uv
- Docker Desktop with Compose v2

The versions intentionally avoid using the host's newer Python for dependencies that may not yet support it.

## Run locally

```bash
cp .env.example .env
docker compose up --build
```

- Web: <http://localhost:5173>
- API health: <http://localhost:8000/healthz>
- Import API: `POST /import-jobs`, then poll `GET /import-jobs/{id}`
- PostgreSQL: `localhost:55432`

The `migrate` service applies Alembic before the API and worker start. The worker claims jobs with `FOR UPDATE SKIP LOCKED`; it does not use Redis or Celery. Raw ingestion stops at `awaiting_mapping` until D0 approves a source-to-canonical mapping.

The [import contract](docs/import-contract.md) defines accepted source types, configurable limits, idempotent retries, state transitions, and validation persistence.
The [mapping review contract](docs/mapping-review-contract.md) defines versioned mapping proposals and attributable, immutable review decisions.
The [canonical promotion contract](docs/canonical-promotion-contract.md) defines the real-evidence activation boundary and raw-row lineage.

For host development:

```bash
uv sync --dev
DATABASE_URL=postgresql+psycopg://sales_app:local_only_change_me@localhost:55432/sales_intelligence uv run alembic upgrade head
uv run uvicorn services.api.main:app --reload
DATABASE_URL=postgresql+psycopg://sales_app:local_only_change_me@localhost:55432/sales_intelligence uv run python -m services.worker.main --once
pnpm install --frozen-lockfile
pnpm --filter @b2b/web dev
```

## D0 audit

The workbook is a collection/audit guide, not a frozen upload contract. Validate its structure without treating it as real evidence:

```bash
uv run d0-audit --template data/templates/Resume_Project_03_Sample_Data_Template.xlsx
```

Core checks live in `packages/domain/b2b_domain/audit.py`; `notebooks/d0_data_audit.ipynb` is only a thin entry point. All D0 decision documents currently say **Pending real anonymized data**. Use the [delivery checklist](docs/data_audit/real_anonymized_data_delivery_checklist.md) before placing any private source files under `data/raw/`.

To exercise the complete synthetic D0 boundary set:

```bash
uv run d0-audit \
  --template data/templates/Resume_Project_03_Sample_Data_Template.xlsx \
  --canonical-dir tests/fixtures/synthetic \
  --evidence-kind synthetic
```

Critical issues map to `reject`, warnings to `quarantine`, and informational findings to `flag`. Empty/unknown values are preserved separately from numeric zero throughout raw ingestion and audit summaries.

## Quality gates

```bash
uv run ruff check .
uv run mypy packages/domain services/api services/worker
uv run pytest
pnpm lint
pnpm test
pnpm build
pnpm test:e2e
docker compose config
docker compose build api worker web
```

## Archived source artifacts

The original root-level files were moved, not duplicated:

| Artifact | SHA-256 |
|---|---|
| `docs/Resume_Project_03_Codex_Handoff.md` | `9a19df1249ff2486bb1a18df6158073be6895a93e6f1ef5f8f96251710cefcd2` |
| `data/templates/Resume_Project_03_Sample_Data_Template.xlsx` | `089a6c273109ee35e67e82132e9baa029d5ac6d11830392c27c92ff23839ef5b` |

The same values are recorded in `docs/artifact_sha256.txt` for command-line verification.
