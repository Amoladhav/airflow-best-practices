# Project guidance

This repository demonstrates an Airflow sales pipeline with reproducible
quality gates, idempotent loading, environment isolation, and deployment
promotion. Local execution comes first; AWS validation is the final phase.

## Assistance style

- Work on the requested function or increment; do not implement unrelated files.
- The developer owns implementation and learning. Explain consequential
  design decisions and provide focused suggestions.
- Follow existing code and tests. Identify conflicting requirements explicitly.
- Prefer simple, readable solutions over frameworks or speculative abstractions.
- Never claim tests or deployments passed without execution evidence.

## Architecture

- Keep business logic in src/sales_lab and orchestration in dags.
- Keep validation and transformation independent of Airflow and storage.
- Perform I/O at explicit boundaries, not during module import.
- Inject environment-specific paths and settings.
- Do not assume separate Airflow tasks share a worker filesystem.
- Pass small identifiers or durable storage references through XCom.
- Treat SQLite as the local storage adapter, not an assumed AWS database.
- Keep Spark separate from the Airflow process and DAG parsing.

## Python and data contracts

- Use type annotations for function inputs and return values.
- Use immutable typed records where they clarify a data contract.
- Use Decimal for monetary parsing and integer cents for stored amounts.
- Reject invalid input explicitly; never silently round, discard, or repair it.
- Require positive sale IDs, valid YYYY-MM-DD dates, nonempty customer IDs,
  and nonnegative amounts with at most two decimal places.
- Reject duplicate sale IDs within a batch.
- Validate the whole batch before writing.
- Use meaningful exceptions with field or row context; avoid logging raw records.
- Catch specific exceptions and preserve their causes.
- Keep comments focused on intent, constraints, and non-obvious decisions.

## SQL and reliability

- Parameterize values; never interpolate input into SQL.
- Keep SQL statements in sql/.
- Load each batch transactionally.
- Replaying identical input must leave the stored result unchanged.
- Changed values for an existing sale ID must update that record.
- Test rollback and recovery as well as successful execution.
- Do not imply that UPSERT alone guarantees every form of idempotency.

## Airflow

- Use the public airflow.sdk authoring API for Airflow 3.
- Keep DAG module scope free of network, database, and filesystem operations.
- Set scheduling, catchup, retries, and execution timeouts explicitly.
- Design tasks to tolerate retries.
- Verify APIs against the project's pinned runtime and provider versions.

## Testing and delivery

- Test observable behavior, boundaries, and failure cases.
- Use temporary storage for tests; never modify development data.
- Mock external service boundaries, not the business logic under test.
- Distinguish unit tests, database integration, DAG import, runtime smoke,
  hosted CI, and AWS acceptance.
- Reuse repository check commands in CI.
- Never silently skip a required check because a dependency is missing.
- Keep credentials, local paths, generated data, and runtime state out of Git.
- Do not provision cloud resources, push, or deploy unless explicitly requested.
- Keep documentation factual: distinguish planned from implemented and verified.