# Local Airflow runtime

## Purpose

This Compose runtime executes the sales DAG locally using Airflow 3.3.2
and Python 3.12. The Dockerfile pins the base image by digest.

The Compose project is named sales-lab-afl105. It provides an isolated
smoke runtime with persistent metadata and sales output.

## Prerequisites and image

Run commands from the repository root with Docker and Docker Compose
available. The application image is airflow-sales-lab:afl105.

Application code and packaged SQL are installed into the image.
Changes to src/ require rebuilding the image before execution.

DAGs, sample data, and scripts are mounted read-only from the repository.
Changes to these files are available to the next container without rebuilding.

## Execution sequence

Run these commands from the repository root.

Initialize Airflow's metadata tables:

```bash
make airflow-init
```

Expected: `Database migration done!`. This prepares metadata; it does not
execute the sales pipeline.

Execute the sales DAG:

```bash
make airflow-smoke
```

Expected: the DAG finishes with `state=success`.

Inspect the persisted sales output:

```bash
make airflow-inspect
```

Expected: eight rows ordered by sale ID, with amounts stored as integer cents.
This reads the database from a fresh container, confirming that output
persists after the execution container exits.

## Replay verification

After the first successful execution and inspection, run the same input again:

```bash
make airflow-smoke
```

Expected: `state=success`.

Inspect the stored output again:

```bash
make airflow-inspect
```

Compare all fields against the first inspection. All eight rows must remain
identical. Row count alone cannot detect changed values.

## Deliberate failure

Override the CSV path for one run with a nonexistent file:

```bash
docker compose run --rm -e SALES_CSV_PATH=/opt/airflow/sample_data/missing.csv airflow-smoke airflow dags test sales_etl
```

Expected: `FileNotFoundError`, retries, and a final DAG state of `failed`.
An intermediate `up_for_retry` state is not the final result. Allow the
configured retries to finish.

This override applies only to this container; it does not edit Compose
configuration or the sample CSV.

Inspect the database afterward:

```bash
make airflow-inspect
```

Expected: the same eight complete rows remain unchanged. This demonstrates
preservation after an input-read failure. Transaction rollback is covered
separately by the SQLite integration tests.





## Storage lifecycle

The airflow-state named volume is mounted at /opt/airflow:

- airflow.db stores Airflow metadata, including DAG runs and task states.
- sales.db stores the sales pipeline output.

Compose scopes the volume to the sales-lab-afl105 project.
The --rm option removes each one-off container after execution but preserves
the named volume. Removing that volume would delete both databases.

## Verified evidence and limits

Verified locally in the pinned container runtime:

- Metadata initialization completed successfully.
- The sales DAG completed successfully.
- A fresh container read all eight expected sales records.
- Replaying identical input left all eight records unchanged.
- A missing CSV caused retries and a final failed DAG state.
- The previously stored records remained unchanged after that failure.
- make airflow-inspect reproduced the expected output.

The smoke command uses airflow dags test without --use-executor.
It executes the DAG locally; it does not establish scheduler-driven,
distributed-worker, or deployed-environment acceptance.

The downstream checker verifies expected records but permits additional
historical records. The separate inspection confirmed the exact eight-row
result for this sample.

SQLite and shared local storage are lab choices. Separate dev/test/prod
environments, automated CI/CD, and AWS acceptance remain pending.
