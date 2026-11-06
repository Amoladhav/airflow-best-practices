# Local Airflow runtime

## Purpose

This Compose runtime executes the sales DAG locally using Airflow 3.3.2
and Python 3.12. The Dockerfile pins the base image by digest.

`compose.yaml` defines the `sales-lab-afl105` smoke runtime with persistent
metadata and sales output. The smoke instructions below apply to that file.
`compose.runtime.yaml` defines the separate scheduler environments documented
later in this guide.

## Common scheduler commands

Run from the repository root. `ENV` accepts `dev`, `test` or `prod` and defaults
to `dev`. Each target selects that environment's existing public settings,
secret file and explicit Compose project. Secret values are not printed by the
configuration check. These commands do not bootstrap inputs or secrets.

| Command | Purpose |
|---|---|
| `make help` | List common operations |
| `make config ENV=dev` | Validate Compose configuration silently |
| `make up ENV=dev` | Start services or apply configuration without rebuilding |
| `make ps ENV=dev` | Show running and stopped containers |
| `make logs ENV=dev` | Follow the scheduler's last 100 log lines and new output |
| `make logs ENV=dev SERVICE=airflow-dag-processor` | Follow a different service |
| `make shell ENV=dev` | Open bash in the running scheduler |
| `make db-shell ENV=dev` | Open psql against Airflow's PostgreSQL metadata |
| `make db-query ENV=dev SQL_FILE=path/to/query.sql` | Execute a local SQL file against metadata |
| `make inspect ENV=dev` | Inspect the separate SQLite sales output |
| `make stop ENV=dev` | Stop services, retaining containers and named volumes |
| `make down ENV=dev` | Remove containers/network, retaining named volumes |
| `make db-start ENV=dev` | Start the existing PostgreSQL container only; requires prior environment initialization |

Use `stop` for an ordinary pause. `down` removes container-local files, including
the generated SimpleAuthManager password file in the API container; its login
may change when recreated. Named sales, metadata and log volumes remain intact.
No target deletes volumes, resets databases, prunes Docker or overwrites inputs.
Logs can contain operational details; inspect them locally before sharing.

`shell` and `logs` accept `SERVICE`; its default is `airflow-scheduler`.
`db-shell` and `db-query` require the selected environment's PostgreSQL service
to be running. No host PostgreSQL installation or exposed database port is needed.

### Query Airflow metadata

PostgreSQL stores DAG/task execution metadata. Business sales rows are in SQLite,
so use `make inspect` for the sales result rather than looking for a PostgreSQL
`sales` table.

Open the metadata console:

```bash
make db-shell ENV=dev
```

At the psql prompt, confirm the database:

```sql
SELECT current_database(), current_user;
```

Check the default transaction mode:

```sql
SHOW default_transaction_read_only;
```

List tables:

```text
\dt
```

Inspect the DAG-run schema before writing queries against it:

```text
\d dag_run
```

Summarize recorded execution states:

```sql
SELECT dag_id, state, COUNT(*) AS runs
FROM dag_run
GROUP BY dag_id, state
ORDER BY dag_id, state;
```

Exit the console:

```text
\q
```

Both database targets set a read-only transaction default for that connection;
they do not change Airflow's own connections. This is an accidental-write guard,
not a restricted database role: the existing lab account can override it. Use
Airflow's supported interfaces for changing execution state. `db-query` disables
the TTY, reads the SQL file through stdin and fails on SQL errors. Both targets
ignore psql startup files with `-X`.

Wrapper validation: local checks with a stub Docker executable verified routing
for all three environments, invalid-environment rejection, SQL-file stdin handling,
missing-file rejection, service selection and command-failure propagation.

Owner verified live dev metadata access on 2026-11-05: after starting the existing
PostgreSQL container directly with Compose, `make db-shell ENV=dev` connected
successfully. The query returned database `airflow`, user `airflow`, and
`default_transaction_read_only=on`. The owner then invoked `make db-start ENV=dev`
against the already-running container with no reported error, and verified
`make db-query ENV=dev SQL_FILE=/tmp/airflow-metadata-check.sql` returned the same
database, user and read-only setting. The wrapper's stopped-to-running transition
was not separately exercised. Existing scheduler/data acceptance below remains
separate historical runtime evidence.

Implementation references: [Compose exec](https://docs.docker.com/reference/cli/docker/compose/exec/),
[Compose down](https://docs.docker.com/reference/cli/docker/compose/down/),
[PostgreSQL psql](https://www.postgresql.org/docs/16/app-psql.html) and
[transaction defaults](https://www.postgresql.org/docs/16/runtime-config-client.html).

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

Development's configuration was subsequently applied with `up -d`. A temporary
marker in `data/dev/input` was visible inside its scheduler, verifying the input
mapping despite Docker Desktop's translated WSL source path. Mount inspection
confirmed read-only access. A fresh-container inspection then returned all eight
original sales rows, including sale 1 at `1995` cents. No DAG replay was repeated
for this mount change; the historical scheduler runs used the original input mount.

### Remaining acceptance limits

Deployment identity recording, separate code releases, automated CI/CD
and promotion remain pending. All runtimes currently share live repository DAGs
and scripts and reuse `airflow-sales-lab:afl105`; the current Git HEAD alone does
not identify the installed application image. The procedures above document
operation, not an automated deployment system.

SQLite and shared local storage are lab choices. Distributed-worker behavior,
production security and AWS compatibility have not been established. AWS
selection and validation remain the final phase.

The proposed [functional changes and code-backout scenarios](change-delivery-and-backout.md)
describe future release acceptance, branch reconciliation and portability contracts.
They are design documentation, not completed runtime evidence.
