# Local Airflow runtime

## Purpose

This Compose runtime executes the sales DAG locally using Airflow 3.3.2
and Python 3.12. The Dockerfile pins the base image by digest.

`compose.yaml` defines the `sales-lab-afl105` smoke runtime with persistent
metadata and sales output. The smoke instructions below apply to that file.
`compose.runtime.yaml` defines the separate scheduler environments documented
later in this guide.

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

## Scheduler environments

These are local learning environments using LocalExecutor, not a production
hosting deployment. All three reuse the application image and the repository's
DAGs and scripts. Separate runtime state does not yet mean separate code releases.

| Environment | Compose project | Loopback UI port | Host input directory |
|---|---|---:|---|
| dev | `airflow-dev` | 8081 | `data/dev/input` |
| test | `airflow-test` | 8082 | `data/test/input` |
| prod | `airflow-prod` | 8083 | `data/prod/input` |

Each project owns its own `postgres-data`, `sales-data` and `airflow-logs`
volumes, such as `airflow-test_sales-data`. PostgreSQL stores Airflow metadata;
the sales volume stores `/opt/airflow/sales-data/sales.db`. Each environment
mounts its input directory read-only at `/opt/airflow/sample_data`. Identical
container paths refer to different host inputs and output volumes.

### Prepare inputs and secrets

Run from the repository root. Create the input directories:

```bash
mkdir -p data/dev/input data/test/input data/prod/input
```

Seed independent files from the repository fixture, preserving existing inputs:

```bash
for env in dev test prod; do cp -n sample_data/sales.csv "data/$env/input/sales.csv"; done
```

Do not copy an environment's database into another environment. `data/` is
Git-ignored. Keep each input unchanged while its DAG run or retries are active.

Each environment needs an independent JWT secret in
`environments/.env.<environment>.secrets`. These files are Git-ignored.
For a fresh environment only, set `runtime_env` below and run this bootstrap.
It creates a file with owner-only permissions, refuses to overwrite an existing
secret, and does not print the secret. Preserve existing development credentials.

```bash
python3 - <<'PYCODE'
import os
import secrets
from pathlib import Path

runtime_env = "test"  # Choose dev, test or prod before running.
path = Path("environments") / f".env.{runtime_env}.secrets"
fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd, "w") as file:
    file.write(f"AIRFLOW_JWT_SECRET={secrets.token_hex(32)}\n")
print(f"{runtime_env}: secret file created")
PYCODE
```

### Validate and start

The following commands target test. For dev or prod, replace both environment
file names consistently. Avoid overriding `COMPOSE_PROJECT_NAME` with `-p` or
shell settings: the selected public environment file defines the namespace.
Run stacks on demand if memory is limited.

Validate without printing resolved configuration or secrets:

```bash
docker compose --env-file environments/test.env --env-file environments/.env.test.secrets -f compose.runtime.yaml config --quiet
```

Start the scheduler stack:

```bash
docker compose --env-file environments/test.env --env-file environments/.env.test.secrets -f compose.runtime.yaml up -d
```

Inspect startup:

```bash
docker compose --env-file environments/test.env --env-file environments/.env.test.secrets -f compose.runtime.yaml ps -a
```

Expected: PostgreSQL and API healthy, volume and metadata initializers
`Exited (0)`, scheduler and DAG processor running. The initializer prepares
volume ownership before regular Airflow services use the volumes.
Test's UI is at `http://localhost:8082`. SimpleAuthManager login was verified
in development; passwords must be retrieved locally, never pasted into reports.
Generated login-password persistence across API-container recreation is not
implemented. The JWT secret file is not a UI password.

### Inspect, trigger and verify

Before the first run of a newly created environment, inspect its history:

```bash
docker compose --env-file environments/test.env --env-file environments/.env.test.secrets -f compose.runtime.yaml exec airflow-scheduler airflow dags list-runs sales_etl
```

Expected for a fresh environment: `No data found`. Existing environments retain
history; do not clear it to recreate this acceptance check.

Check whether output already exists without creating a database:

```bash
docker compose --env-file environments/test.env --env-file environments/.env.test.secrets -f compose.runtime.yaml exec airflow-scheduler python -c 'import os; from pathlib import Path; print("APP_ENV=" + os.environ["APP_ENV"]); print("sales_database_exists=" + str(Path(os.environ["SALES_DB_PATH"]).exists()))'
```

Expected for a fresh test environment: `APP_ENV=test` and
`sales_database_exists=False`.

Unpause the DAG:

```bash
docker compose --env-file environments/test.env --env-file environments/.env.test.secrets -f compose.runtime.yaml exec airflow-scheduler airflow dags unpause sales_etl
```

The immediate unpause output displayed `True` during acceptance. Inspect the
stored state and confirm `False` before triggering:

```bash
docker compose --env-file environments/test.env --env-file environments/.env.test.secrets -f compose.runtime.yaml exec airflow-scheduler airflow dags list
```

Trigger a run using a new, unique run ID each time:

```bash
docker compose --env-file environments/test.env --env-file environments/.env.test.secrets -f compose.runtime.yaml exec airflow-scheduler airflow dags trigger --run-id example_test_001 sales_etl
```

A queued response confirms submission, not completion. Check both tasks:

```bash
docker compose --env-file environments/test.env --env-file environments/.env.test.secrets -f compose.runtime.yaml exec airflow-scheduler airflow tasks states-for-dag-run sales_etl example_test_001
```

Expected: `ingest_and_load` and `check_loaded_sales` both reach `success`.
If triggered through the UI, use the actual generated run ID from `list-runs`.

Inspect persisted contents through a fresh container:

```bash
docker compose --env-file environments/test.env --env-file environments/.env.test.secrets -f compose.runtime.yaml run --rm --no-deps airflow-init python /opt/airflow/scripts/inspect_sales.py
```

This overrides the initializer's command with the read-only inspection script;
it does not migrate metadata. Compare every field against the chosen input.
For identical replay, trigger again with a different run ID and unchanged input,
verify both tasks, then compare all persisted rows. Do not rerun already completed
acceptance checks unless a change gives a reason to do so.

### Stop without deleting data

Stop a selected stack when finished:

```bash
docker compose --env-file environments/test.env --env-file environments/.env.test.secrets -f compose.runtime.yaml stop
```

This preserves containers and named volumes. `up -d` starts it again and applies
configuration changes when needed. Do not use `down --volumes` or volume pruning
when preserving this lab's data. The separate smoke runtime is unchanged.

### Verified scheduler and isolation evidence

Owner-run acceptance established:

- Development completed two scheduler runs with identical eight-row output.
- Test and prod initially had no DAG runs and no sales database.
- Test and prod each completed both DAG tasks successfully through the scheduler.
- Test's first output contained all eight original sample rows.
- Changing only test's sale 1 input from `19.95` to `20.95`, then executing a
  second successful run, produced `2095` cents with the other seven rows unchanged.
- Subsequent development inspection and prod execution/inspection both returned
  the eight original rows, with sale 1 still at `1995` cents.

| Environment | Verified run IDs | Persisted sale 1 |
|---|---|---:|
| dev | `afl106_scheduler_001`, `afl106_scheduler_002` | 1995 cents |
| test | `afl106_test_001`, `manual__2026-11-05T01:38:12.400750+00:00` | 2095 cents after change |
| prod | `manual__2026-11-05T01:43:55.005833+00:00` | 1995 cents |

The test fixture intentionally remains different after this isolation exercise.
The run IDs above are historical evidence, not IDs to reuse in future commands.

### Remaining acceptance limits

Development's running services have not yet been recreated with the new
`data/dev/input` mount. Its successful historical runs used the original
`sample_data` mount; its persisted data was checked after the test-only update.

Environment code-SHA recording, separate release directories, automated CI/CD
and promotion remain pending. All runtimes currently share live repository DAGs
and scripts and reuse `airflow-sales-lab:afl105`; the current Git HEAD alone does
not identify the installed application image. The procedures above document
operation, not an automated deployment system.

SQLite and shared local storage are lab choices. Distributed-worker behavior,
production security and AWS compatibility have not been established. AWS
selection and validation remain the final phase.
