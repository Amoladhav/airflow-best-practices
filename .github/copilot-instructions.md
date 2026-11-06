# Data Engineering Stack Guidelines

## General Principles
- **Idempotency & Safety:** Write deterministic code that handles retries cleanly. Never hardcode secrets, credentials, or connection strings; always use the environment's secret manager or configuration bindings.
- **Modularity:** Keep orchestration, transformation logic, compute execution, and infrastructure cleanly separated.

---

## Stack-Specific Standards

### 1. Orchestration (Airflow)
- **TaskFlow Paradigm:** Prefer native task decorators (`@dag`, `@task`, `@task_group`) over legacy operator-heavy definitions.
- **Data Passing:** Pass small payloads or references via context/XComs; store large datasets or intermediate states in object storage or data lakes, not inline execution memory.
- **Top-Level Code:** Keep DAG parsing files free of heavy computation, database connections, or external API calls during import time.

### 2. Transformation & Modeling (dbt)
- **Layered Architecture:** Structure models cleanly through staged (`stg_`), intermediate (`int_`), and final fact/dimension mart (`fct_`, `dim_`) layers.
- **Dependency Graph:** Always use standard referencing functions (`ref` and `source`) to build automated lineage DAGs.

### 3. Compute & Data Processing (Spark / SQL)
- **Optimized Execution:** Avoid collecting or materializing large distributed datasets to driver memory (avoid excessive `.collect()` or dataframe-to-local conversions).
- **Format Standards:** Leverage columnar and transactional table formats (e.g., Delta) for persistence, schema enforcement, and atomic upserts.
- **SQL Convention:** Write SQL keywords in uppercase (`SELECT`, `FROM`, `WHERE`, `JOIN`) and maintain clean table aliasing. Use `WHERE` clause by default to limit scope.

### 4. Infrastructure & Scripting (AWS, Bash, Notebooks)
- **Shell Scripts:** Ensure robust error handling on shell scripts (e.g., exit immediately on errors and pipe failures).
- **Notebooks (`.ipynb`):** Maintain clear structural separation across cells (imports, configuration, core execution, validation) and avoid leaving dangling debug variables in committed notebooks.
