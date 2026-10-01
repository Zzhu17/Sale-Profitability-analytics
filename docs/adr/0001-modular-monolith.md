# ADR 0001: Production-shaped modular monolith

- Status: Accepted (Locked direction)
- Date: 2026-10-01

## Decision

Use a monorepo with a React/Vite web app, FastAPI API, separate batch worker, shared Python domain package, PostgreSQL, and Alembic. Keep service and repository boundaries inside a modular monolith. Reserve dbt and ML directories without implementing unvalidated contracts.

## Consequences

- One codebase supports the public synthetic demo and private pilot while data stores and deployment settings remain separate.
- Batch imports and later scoring run outside API requests.
- Microservices, Kafka, Kubernetes, online feature stores, and online model serving are excluded until evidence demonstrates a need.
