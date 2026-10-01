# Resume Project 03 — Codex Development Handoff

> Updated: 2026-10-01
> Project status: product direction and engineering direction are ready; begin with Sprint 0 and D0 Data Audit. Data-dependent contracts and ML choices remain intentionally provisional until a real anonymized sample is audited.

## 0. Instructions for the next Codex session

Treat this document as the current project baseline.

- Items marked **Locked** are settled decisions. Do not reopen them unless new evidence creates a concrete conflict.
- Items marked **Provisional** must be decided from the real data audit; do not silently convert them into final requirements.
- The user wants rigorous engineering depth, not a superficial collection of resume keywords.
- Do not invent business metrics, model lift, user adoption, or production claims before they are measured.
- Do not use synthetic data as evidence of real-world model performance.
- Work incrementally, test each stage, and explain material tradeoffs before making irreversible architecture changes.
- The next active phase is **Sprint 0 — Data Audit & Engineering Foundation**.

## 1. Portfolio context and purpose

The user is building three major resume projects for Data Science / AI Engineering / software-oriented roles:

1. **ForecastServe** — time-series forecasting and multi-model evaluation.
2. **PortFlow Industrial** — industrial operations, full-stack engineering, routing, Kafka/WebSocket, Docker/Kubernetes.
3. **This project** — business problem framing, messy business data, profitability analytics, ranking/ML, decision support, testing, CI/CD, and deployable product engineering.

Project 03 must therefore emphasize:

> Data quality + auditable analytics + decision science + product workflow + production-shaped engineering.

It should not add LLM, RAG, multi-agent, or autonomous action merely to increase technical breadth; those would blur the project's role in the portfolio.

## 2. Product identity — Locked

### Working name

**B2B Sales Profitability Intelligence Platform**

### Product strategy

**Vertical-first, configurable product**:

- Initial vertical/reference case: B2B wholesale/distribution, specifically tire distribution.
- It is not a generic QuickBooks clone.
- It is not a one-off script that only works for one company.
- Core entities and business rules should remain configurable enough to transfer to adjacent distributors.

### Primary users

- Field Salesperson
- Account Manager

### Secondary user

- Sales Manager / Admin

### Core job-to-be-done

> “Which existing accounts warrant my review today, and why?”

Use **accounts warranting review** in product language. Do not claim that the system identifies customers whose contact will necessarily create incremental orders.

### Product boundary

This is a **decision-support product**. It does not:

- guarantee that a salesperson follows a recommendation;
- guarantee that contacting a customer creates an incremental order;
- replace the CRM;
- autonomously contact customers;
- autonomously change prices, orders, or inventory.

The system is responsible for identifying and explaining credible opportunities using information known at the scoring time.

## 3. Three official hypotheses — Locked

### H1 — Recommendation Scope

The system identifies reorder, reactivation, and high-profit accounts worth reviewing, but does not claim that sales contact necessarily creates incremental orders.

### H2 — Adoption Hypothesis

Accurate, timely, explainable recommendations with actionable inventory support are expected to improve salespeople's willingness to view and record recommendations. This is a hypothesis that requires lightweight user testing and a pilot; it is not an established fact.

### H3 — Data Strategy

- Real historical data is used for model training, temporal validation, baseline comparison, and real performance conclusions.
- Synthetic data is used only for public demos, automated tests, edge cases, and controlled pipeline sanity checks.
- Synthetic data must not be used to inflate the sample and then claim improved real-business performance.

## 4. Business problem and expected workflow — Locked

Current business problems:

1. Salespeople largely rely on personal memory and subjective judgment when deciding which existing customer to review.
2. Revenue alone hides margin erosion from costs, discounts, returns, and potentially delivery/handling.
3. There is no structured recommendation → action → outcome trail for evaluating and improving decisions.

Target workflow:

```text
Import source files
→ Validate and map entities
→ Calculate auditable profitability
→ Generate review candidates and rankings
→ Explain each recommendation
→ Inspect Customer 360
→ Record action / feedback / outcome
→ Evaluate recommendation performance
```

Sales actions may include:

- Call
- Visit
- Email
- Follow Up Later
- Skip

Outcomes should include negative and neutral outcomes as well as positive ones:

- Interested
- Quote Requested
- No Current Demand
- Order Placed
- No Response
- Not Relevant

Only logging positive results would create selection bias, so `No Response` and `No Current Demand` must remain available.

## 5. MVP scope — Locked at the product level

### P0 — Must complete

1. Excel/CSV import and validation framework
2. Customer and product mapping/review
3. Auditable observed profitability engine
4. Rule-based overdue/reorder alerts
5. Inventory eligibility/filtering
6. Customer 360
7. Recommendation lifecycle and action/outcome logging
8. Limited admin profitability analytics
9. Dockerized local environment, core automated tests, and CI

### P1 — Add only after the data audit supports it

1. Purchase-propensity model
2. Expected Profitable Opportunity ranking
3. Expanding-window temporal backtesting
4. Baseline comparison
5. Deterministic reason codes tied to model/rule outputs

### P2 — Portfolio and deployment completion

1. Public demo with synthetic data
2. Private/internal pilot configuration
3. AWS/Terraform deployment if time and budget permit
4. Architecture and model documentation
5. Demo video and measured resume bullets

### Explicitly outside MVP

- QuickBooks API integration
- Full CRM replacement
- Lead generation
- Uplift or causal modeling
- Dynamic pricing
- Route optimization
- Product-level purchase prediction
- Autonomous sales actions
- Real-time streaming
- Multi-tenant product implementation
- LLM, RAG, Agent, or MCP features

## 6. Recommendation design — Locked structure, provisional thresholds

Do not start with one opaque total score. Use the following structure:

```text
Eligibility filters
→ Opportunity type
→ Priority/ranking score
→ Business warnings
→ Recommendation lifecycle
```

### Eligibility filters

Expected examples:

- Account belongs to the current sales rep.
- Account has sufficient history for the relevant rule/model.
- Account has not just placed a qualifying order.
- Historically relevant products are not all out of stock.
- Account is not on a do-not-contact, inactive, or credit-hold list when those fields exist.

The exact minimum order count and recent-order exclusion window remain **Provisional** pending D0.

### Opportunity types

- **Overdue / Reorder Review**
- **Reactivation**
- **High-Profit Opportunity** — only if supported by data/model evidence

Dormant customers must not be silently excluded. They should enter a separate Reactivation queue so they are not mixed with normal reorder candidates.

### Ranking

Long-term target:

```text
Expected Profitable Opportunity
= P(Purchase within the selected horizon)
× Expected Observed Contribution Profit
```

Before ML is justified, rank with transparent baselines such as overdue ratio, recency, frequency, historical profitability, or a documented composite rule.

### Warnings, not positive opportunity boosts

- Margin Risk
- Partial Stockout
- Outstanding Balance
- Credit Risk / Credit Hold

Margin Risk is not automatically a reason to contact someone. If the sales rep cannot act on detailed costs, show a limited “quote carefully” warning to the rep and keep detailed margin analysis in the Admin view.

### Recommendation lifecycle

Prevent the same account from appearing as a fresh recommendation every day:

- New
- Viewed
- Contacted
- Snoozed
- Resolved
- Expired

Preserve recommendation snapshots with score, rank, reasons, model/rule version, scoring time, and feature/profit contract version.

## 7. Inventory logic — Direction locked, implementation provisional

Use historical product affinity to identify products relevant to an account.

```text
All relevant products unavailable
→ suppress from the normal recommendation queue

Some relevant products available
→ retain the account and display a partial-stock warning
```

Inventory is initially a business eligibility/filtering input; it does not have to be a feature in the propensity model.

All training and scoring features must obey:

```text
inventory_timestamp <= scoring_timestamp
```

The exact affinity definition—top products, share threshold, recency weighting, or category-level fallback—remains **Provisional** pending D0.

## 8. Profitability contract — Direction locked, exact formula provisional

Profitability must be deterministic, auditable, and implemented in SQL/Python rules, not hidden inside ML.

Ideal contribution formula:

```text
Revenue
- Product Cost / COGS
- Discount not already reflected in net line price
- Delivery / Freight Cost
- Handling Cost
- Return Loss
= Contribution Profit
```

However, unavailable costs must not be invented. If outbound delivery/handling is missing, the MVP metric must be named honestly, for example:

> **Observed Contribution Profit Before Outbound Delivery**

Required outputs:

- Order-level revenue, COGS, observed profit, and margin
- Customer-level lifetime/recent revenue and observed profit
- Product-level revenue and observed profit where cost reliability permits
- Unallocated return amount
- Data-quality/coverage flags

Before freezing the formula, manually reconcile 20–30 sampled invoices against the source accounting report and document discrepancies from tax, discounts, returns, or cost timing.

## 9. Existing sample workbook and its purpose

An Excel sample/data-collection template already exists:

`Resume_Project_03_Sample_Data_Template.xlsx`

Current local path at handoff time:

`/workspace/scratch/29835c63d88c/outputs/resume_project03_sample_template/Resume_Project_03_Sample_Data_Template.xlsx`

It contains:

- Start Here / instructions
- Field guide / data dictionary
- Sales Reps
- Customers
- Products
- Invoices
- Invoice Items
- Returns
- Daily Inventory
- Optional Purchase Batches

Important interpretation:

- This workbook is an audit and data-preparation guide, not a frozen production upload format.
- Real source files may be flat QuickBooks exports plus separate inventory/returns files.
- The application should eventually use source-specific adapters that map raw exports into a canonical model.
- Do not require the user to manually normalize every historical source file into seven perfect tables before ingestion.

For a real sample, preserve raw errors and variation. Remove unnecessary PII, use stable anonymous IDs, keep all statuses and dates, and do not convert unknown values to zero.

## 10. D0 Data Audit — Immediate analytical work

The audit must establish evidence before modeling.

### 10.1 Grain, keys, and relationships

Confirm the grain and uniqueness of every source/table:

- one row per invoice vs one row per invoice line;
- stable invoice and line identifiers;
- customer and product references;
- duplicate rows and repeated exports;
- return and inventory linkage;
- date and monetary-field parseability.

### 10.2 Customer and product entity resolution

First use safe deterministic normalization:

- trim whitespace;
- collapse repeated spaces;
- normalize case and punctuation;
- normalize known abbreviations.

Then generate fuzzy-match candidates using edit distance, token similarity, and available auxiliary fields. The system may suggest matches, but high-risk records require human confirmation.

Maintain:

```text
internal_id
canonical_name
original_name
match_method
match_confidence
review_status
```

Entity mapping is an ongoing data-management capability, not a one-time cleanup.

### 10.3 Customer order distribution

Measure, rather than assume:

- valid invoice count per customer;
- first/last purchase;
- active months;
- adjacent order gaps;
- average/median order value;
- frequently purchased products;
- returns;
- reorder within candidate horizons.

Inspect buckets such as 1, 2, 3–5, 6–10, and >10 orders.

Provisional interpretation:

- 1 order: Cold Start; no personalized reorder estimate.
- 2 orders: insufficient for an individual cycle.
- 3+ orders: basic gap statistics may be possible.
- 4+ orders: more suitable for a customer-specific median interval.

These are starting rules, not final thresholds.

### 10.4 Prediction/label window

Compute actual gap distributions and evaluate 14-, 30-, 60-, and 90-day labels.

For each horizon, inspect:

- eligible customers;
- positive rate and positive-event count;
- usable training/backtest periods;
- business lead time;
- label censoring at the end of history.

Because only roughly one year of history is expected, a 90-day label may consume too much of the usable timeline. The likely horizon is 30 or 60 days, but the data must decide.

If customer cycles vary widely, consider:

```text
days_since_last_order / historical_median_reorder_interval
```

as an overdue signal.

### 10.5 Historical cost reliability

Check:

- non-null and positive unit cost;
- sensible quantity and price;
- batch-to-batch cost changes;
- whether historical costs were overwritten by current costs;
- whether `cost × quantity` reconciles with accounting COGS;
- whether calculated revenue and gross profit reconcile on sampled invoices.

If historical costs are unreliable, profitability modeling pauses or is downgraded until the metric is honestly redefined.

### 10.6 Open, Paid, and Void semantics

Build a cross-table using status and available order/delivery/payment dates. Sample real records to determine:

- whether Open means delivered but unpaid;
- whether Paid always means delivered;
- whether Void retains original lines/amounts;
- which timestamp best represents purchase intent.

Provisional purchase-event definition:

```text
status in ('Open', 'Paid')
and status != 'Void'
event_time = order_date
```

This must be validated before it becomes a contract.

### 10.7 Return attribution

Use three levels:

1. Exact original invoice linkage.
2. Unique inferred match for same customer/product in a reasonable prior window, clearly labeled as inferred.
3. Unallocated return retained at customer-product or customer-month level; never fabricate an invoice link.

Separate resellable and damaged/write-off returns if the data supports it.

### 10.8 Inventory history

Build a complete `product_id × calendar_date` coverage matrix and verify:

- missing snapshot vs true zero stock;
- product mapping coverage;
- new-product start dates;
- whether later extracts overwrote history;
- continuity and source timestamps.

### 10.9 Data-quality severity

**Critical / reject or block** examples:

- missing invoice ID or order date;
- invalid positive-sale quantity;
- duplicate invoice line;
- unmapped required customer/product;
- Void included as revenue;
- future dates;
- unparseable monetary values.

**Warning / quarantine or import with flag** examples:

- missing cost;
- missing address/ZIP;
- possible duplicate entity;
- unallocated return;
- missing fulfillment date;
- inventory gaps.

**Informational** examples:

- one-order customer;
- low-frequency product;
- extreme but plausible B2B order.

Use IQR, MAD, and percentile review for amount anomalies. Do not automatically delete B2B long-tail orders using z-scores alone.

### 10.10 Temporal backtesting feasibility

Never randomly split order events. Use expanding-window folds and reserve a final fully observable test window.

For every fold, report:

- eligible customers;
- positive events;
- purchase-rate stability;
- new customers appearing only later;
- customer/segment imbalance;
- label completeness;
- seasonality limitations from a one-year history.

If the final validation/test positives are too few, the project can still evaluate rules and exploratory models, but it must not claim stable production generalization.

## 11. D0 outputs and gates

Expected D0 artifacts:

```text
docs/data_inventory.md
docs/data_dictionary.csv
docs/data_quality_report.md
docs/entity_resolution_rules.md
docs/profitability_contract.md
docs/purchase_event_contract.md
docs/label_window_decision.md
docs/modeling_feasibility.md
data/mappings/customer_mapping.csv
data/mappings/product_mapping.csv
data/quarantine/rejected_rows.csv
notebooks/d0_data_audit.ipynb
```

The audit should issue separate **Pass / Conditional Pass / Fail** judgments for:

1. Customer 360
2. Profitability analytics
3. Reorder-cycle rules
4. Purchase-propensity ML
5. Temporal backtesting

The whole dataset does not need a single pass/fail label.

## 12. Model and evaluation strategy — Locked principles, provisional model

### Baselines first

Compare, in increasing complexity:

1. Random ranking
2. Historical revenue ranking
3. Recency/frequency ranking
4. Reorder-cycle rule
5. Profitability ranking
6. Logistic Regression
7. Tree/boosting model only if data volume and temporal validation justify it
8. Expected Profitable Opportunity ranking

The default first ML model is Logistic Regression because the expected dataset is small. LightGBM/XGBoost is optional, not mandatory.

### Metrics

Offline model metrics:

- PR-AUC and ROC-AUC
- Precision@K / Recall@K
- Calibration

Ranking/business proxy metrics:

- NDCG@K
- Profit@K
- orders/revenue/observed profit captured
- lift over revenue, recency, and reorder-cycle baselines

Product/adoption metrics for a future pilot:

- recommendation view rate;
- contact logging rate;
- closure rate;
- weekly usage;
- duplicate/repeated recommendation rate.

Business outcomes for a future pilot:

- order rate within the attribution window;
- reactivated accounts;
- observed contribution profit after recommendation;
- unavailable-product rate;
- incremental performance vs an appropriate comparison group, if one is eventually designed.

Offline ranking quality is not proof of causal business lift.

## 13. Engineering architecture — Locked direction

### Overall pattern

- Production-shaped modular monolith
- Monorepo
- API / Service / Repository layering where useful
- Batch-first import and scoring
- PostgreSQL as the operational/analytics store for MVP
- No premature microservices

### Primary stack

- Frontend: React + TypeScript + Vite
- Backend: FastAPI + Pydantic + SQLAlchemy
- Database/migrations: PostgreSQL + Alembic
- Analytics: dbt Core where it adds lineage and tests
- File parsing: Polars/Pandas + openpyxl
- Validation: Pandera plus database/dbt tests
- ML: scikit-learn; optional LightGBM/XGBoost after the model gate
- Packaging/local development: Docker + Docker Compose
- Testing: pytest, Vitest/React Testing Library, Playwright, integration tests
- CI: GitHub Actions

### Batch job pattern

For MVP, prefer a PostgreSQL job table plus a separate worker process:

```text
Upload/import request
→ create import job
→ worker validates and loads raw data
→ transform/core/marts
→ feature generation and optional scoring
→ store status and error report
→ frontend polls job status
```

Do not add Redis, Celery, Kafka, Kubernetes, an online feature store, or online model serving without a demonstrated need.

### Suggested repository structure

```text
B2B-Sales-Profitability-Intelligence/
├── apps/web/
├── services/api/
├── services/worker/
├── packages/domain/
├── analytics/dbt/
├── ml/features/
├── ml/training/
├── ml/evaluation/
├── ml/scoring/
├── data/templates/
├── data/raw/
├── data/processed/
├── data/synthetic/
├── tests/fixtures/
├── tests/integration/
├── tests/e2e/
├── docs/adr/
├── docs/data_audit/
├── infra/terraform/
└── docker-compose.yml
```

Raw source data must be immutable and traceable by source file, import batch, file hash, upload time, original row number, validation status, and error reason.

## 14. Deployment separation — Locked

### Public portfolio demo

- Synthetic data only
- Publicly deployable
- Recruiter-accessible
- Demonstrates complete workflow without real customer information

### Internal pilot

- Real anonymized/private business data
- Local or private deployment
- Restricted accounts and stronger retention/access controls

The two environments may share code but must never share real customer data publicly.

AWS/Terraform is P2. A likely later topology is static React hosting, containerized API/worker, managed PostgreSQL, object storage, secrets, logging, and HTTPS—but do not let cloud work delay the validated core product.

## 15. Development plan and current status

### Current readiness

| Area | Status |
|---|---|
| Product definition | Ready |
| MVP scope | Ready |
| User workflow | Ready |
| Three official hypotheses | Locked |
| Engineering direction | Ready |
| Sprint 0 | Ready to start |
| Canonical data contract | Provisional until D0 |
| Profit contract | Provisional until D0 |
| Purchase event and label horizon | Provisional until D0 |
| ML complexity and threshold | Provisional until D0 |
| Business impact claims | Not yet available |

### Sprint 0 — Start now

1. Create the repository/project root in a user-approved accessible location.
2. Move—not duplicate—the handoff document and sample workbook into the project structure when both locations are accessible.
3. Initialize the monorepo and basic README.
4. Set up FastAPI, React/TypeScript, PostgreSQL, and Docker Compose skeletons.
5. Add Ruff, mypy, ESLint, pytest, Vitest, and a minimal GitHub Actions pipeline.
6. Add Alembic migration skeleton.
7. Create raw import job interfaces and immutable lineage fields.
8. Build the D0 audit notebook/scripts against synthetic fixtures and the workbook template.
9. Create ADR and data-contract directories.

Do not build the final model or final dashboard before Gate 1.

### Gate 1 — Real anonymized sample arrives

Complete D0 and freeze:

- source-to-canonical mappings;
- purchase-event contract;
- profitability contract v1;
- label window;
- eligibility rules;
- return attribution rules;
- inventory/product-affinity logic;
- modeling feasibility.

### Sprint 1–3 — Core product

- production import/validation;
- mapping review;
- profitability engine;
- rule-based overdue/reactivation queues;
- inventory eligibility;
- Customer 360;
- recommendation lifecycle;
- action/outcome logging;
- limited admin analytics.

At this point the product should form a complete business workflow even without ML.

### Sprint 4 — Baseline and ML gate

- implement simple baselines;
- build leakage-safe temporal dataset;
- run expanding-window backtests;
- train Logistic Regression;
- test a tree model only if justified;
- compare ranking/business proxy metrics;
- retain rules if ML does not reliably outperform them.

### Sprint 5–6 — Productionization and portfolio delivery

- frontend/backend integration;
- integration and E2E testing;
- security checks;
- public synthetic demo;
- internal/private deployment workflow;
- CI/CD and optional Terraform/AWS;
- architecture, data-quality, and model reports;
- measured resume bullets and demo materials.

## 16. Files currently present at handoff time

Primary deliverables:

- `/workspace/scratch/29835c63d88c/Resume_Project_03_Codex_Handoff.md`
- `/workspace/scratch/29835c63d88c/outputs/resume_project03_sample_template/Resume_Project_03_Sample_Data_Template.xlsx`

Supporting generator:

- `/workspace/scratch/29835c63d88c/build_resume_project03_sample_template.mjs`

The `preview_*.png`, `contact_*.png`, and `.inspect.ndjson` files in the output directory are QA/intermediate artifacts. They are not required in the final project folder unless the next session needs to regenerate or verify the workbook.

The prior request was to place the project on the user's Mac Desktop, but the previous execution environment could not access `/Users/.../Desktop`. Do not create a fake Desktop folder. If Desktop is still not mounted, ask the user to open/add the intended folder as the Codex workspace; otherwise create the project within the accessible workspace.

## 17. Immediate prompt for the next Codex window

Use this after attaching or pasting this document:

> Continue Resume Project 03 using this handoff as the source of truth. Preserve all items marked Locked and treat Provisional items as data-dependent decisions. We are ready to begin Sprint 0, not to redesign the product from scratch. First inspect the accessible workspace and existing handoff/template files. Then propose the exact Sprint 0 repository setup and execution order, identify only genuine blockers, and wait for my confirmation before any material scope change. Do not train a final model or invent performance results before the D0 audit of real anonymized data.

## 18. Target technical narrative—not yet a resume claim

> Built a production-shaped B2B sales decision platform with React, FastAPI, PostgreSQL, and auditable data transformations, combining profitability analytics with leakage-safe offline ranking to identify accounts warranting review; implemented data validation, temporal backtesting, deterministic explanations, action/outcome feedback, automated testing, CI/CD, and separate synthetic-demo/private-data deployment paths.

This is the target narrative only. Convert it into resume bullets after implementation and measurement; never present planned metrics as completed results.
