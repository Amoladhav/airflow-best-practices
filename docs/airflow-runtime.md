# Airflow runtime

Each environment is a separate Docker Compose project. A release image contains
the application, SQL resources, DAGs and scripts; local files contain environment
configuration, secrets and CSV input.

| Environment | Git branch | Compose project | UI | Input directory |
|---|---|---|---|---|
| dev | `dev` | `airflow-dev` | http://localhost:8081 | `data/dev/input` |
| test | `test` | `airflow-test` | http://localhost:8082 | `data/test/input` |
| prod | `main` | `airflow-prod` | http://localhost:8083 | `data/prod/input` |

Each project owns its PostgreSQL metadata, SQLite sales and log volumes. The API
server, scheduler with LocalExecutor, and DAG processor use the same release image.
Initialization containers prepare volume permissions and migrate Airflow metadata.

## Environment appearance

The page header and browser title identify **Sales Lab | DEV**, **Sales Lab | TEST**
or **Sales Lab | PROD**. Navigation uses blue, amber and red respectively.
The explicit titles distinguish environments without relying on color alone.

Each public environment file defines `AIRFLOW_UI_NAME` and `AIRFLOW_UI_THEME`.
Compose passes these to Airflow's built-in `api.instance_name` and `api.theme`
settings; no custom frontend or separate image is needed. Configuration changes
take effect when the API server container is recreated during deployment.
See [Airflow UI customization](https://airflow.apache.org/docs/apache-airflow/3.3.2/howto/customize-ui.html).

## Prepare environment inputs and secrets

Run from the repository root:

```bash
mkdir -p data/dev/input data/test/input data/prod/input
```

Seed missing input files without replacing existing environment data:

```bash
for runtime_env in dev test prod; do cp -n sample_data/sales.csv "data/$runtime_env/input/sales.csv"; done
```

Generate separate JWT secrets for new environments. Existing files are preserved;
secret values are not printed:

```bash
python3 - <<'PY'
import os
import secrets
from pathlib import Path

Path("secrets").mkdir(mode=0o700, exist_ok=True)
for runtime_env in ("dev", "test", "prod"):
    path = Path("secrets") / f"{runtime_env}.env"
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        print(f"{runtime_env}: existing secret preserved")
        continue
    with os.fdopen(fd, "w") as stream:
        stream.write(f"AIRFLOW_JWT_SECRET={secrets.token_hex(32)}\n")
    print(f"{runtime_env}: secret created")
PY
```

Public settings are in `environments/dev.env`, `test.env` and `prod.env`.
Deploy through the [CI/CD workflow](local-cicd.md). Keep each input file unchanged
while its DAG run or retries are active. Never copy an environment's database into
another environment to simulate promotion.

## Connect and inspect

```bash
make status ENV=prod
```

```bash
make airflow-password ENV=prod
```

```bash
make sales ENV=prod
```

```bash
make db-connect ENV=prod
```

The SQL console connects to PostgreSQL **Airflow metadata**, not the SQLite sales
store. It displays `[prod] airflow>` and sets the connection read-only by default.
For example:

```sql
SELECT dag_id, state, COUNT(*) AS runs
FROM dag_run
GROUP BY dag_id, state
ORDER BY dag_id, state;
```

Use `\dt` to list tables, `\d dag_run` for its schema, and `\q` to exit. The lab
account can override its read-only setting; use Airflow interfaces to change run
state. `make sales` opens SQLite read-only and prints sale ID, date, customer and
amount in cents.

```bash
make logs ENV=test SERVICE=airflow-dag-processor
```

These inspection commands select existing containers by Compose labels and need
no image digest. See [credentials and login](secrets.md) for password handling.

## Explicit runtime administration

Runtime Make commands automatically inspect the API server, scheduler and DAG
processor and require a consistent image ID. Stopped containers are supported.
Missing containers or mixed images stop the command; there is no fallback to latest.
For an initial deployment, or after removing containers, use the CI/CD controller.

To apply UI configuration to just the API server:

```bash
make ui-apply ENV=test
```

This reuses the deployed image, waits for health and does not restart dependencies.
API recreation may generate a new UI password.

```bash
make config ENV=dev
```

```bash
make up ENV=dev
```

```bash
make stop ENV=dev
```

Finish active DAG runs before stopping services. `stop` retains containers and
volumes. `down` removes containers/network but preserves named volumes; it also
removes container-local generated login files. Never use volume deletion or image
pruning as a deployment-recovery step. `make platform-stop` stops CI services only,
not Airflow.

The separate `infra/docker/compose.yaml` smoke stack is an isolated development exercise.
Its `airflow-init`, `airflow-smoke` and `airflow-inspect` targets are unrelated to
the dev/test/prod release stacks; see [command reference](commands.md).
