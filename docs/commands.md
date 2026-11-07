# Developer command guide

Run commands from the repository root. `make help` is the short menu. Plain `make`
still runs checks; it never starts infrastructure or deploys a release.

## Daily commands

| Command | What it does |
|---|---|
| `make check` | Ruff, SQLFluff, format verification and Python tests |
| `make format` | Format Python files; review the resulting diff |
| `make platform-start` | Start/resume Gitea, both runners and the webhook receiver |
| `make platform-stop` | Require idle jobs, disable webhook and stop CI services |
| `make platform-status` | Platform containers and recent workflow results |
| `make releases` | Last verified environment releases and latest attempts |
| `make status ENV=prod` | List existing prod containers |
| `make logs ENV=test` | Follow test scheduler logs |
| `make sales ENV=prod` | Read prod SQLite sales rows |
| `make airflow-password ENV=prod` | Print the admin UI password locally; see [secrets](secrets.md) |
| `make db-connect ENV=prod` | Open PostgreSQL Airflow metadata console, read-only default |

`ENV` defaults to `dev`; valid values are `dev`, `test`, `prod`.
`make logs` accepts `SERVICE=airflow-dag-processor` or another Compose service.
`status`, `logs`, `sales` and `db-connect` use Compose labels to locate existing
containers. They need **no image digest or local environment-secret files** and
cannot create/recreate containers. Sales needs a running scheduler; metadata needs
running PostgreSQL. Missing or ambiguous containers fail with an explicit message.
The metadata account can override its read-only session setting; it is not a
restricted database role. Sales inspection opens SQLite with `mode=ro`.

`platform-stop` leaves all three Airflow environments running. No daily command
prunes Docker, removes volumes or resets data. Deployments happen through the
[lifecycle](architecture.md#developer-and-release-lifecycle), not a Make target.

## SQL console

```bash
make db-connect ENV=prod
```

The prompt displays the selected environment and database:

```text
[prod] airflow> SELECT current_database(), current_user;
```

Use `ENV=dev` (default), `ENV=test`, or `ENV=prod`. Continuation lines also show
the environment. Exit with `\q`. This connects to PostgreSQL **Airflow metadata**;
`make sales ENV=prod` reads the separate SQLite business data.

## Setup and advanced operations

| Command | Use |
|---|---|
| `make platform-install` | Publish trusted controller scripts and configure webhook; owner-run setup/update |
| `make lint`, `make format-check`, `make test` | Run individual parts of the check gate |
| `make lint-docker` | Run the existing pinned Hadolint check on the application infra/docker/Dockerfile |
| `make fix` | Apply Ruff fixes; review the diff |
| `make config ENV=dev` | Validate explicit release runtime configuration |
| `make up ENV=dev` | Explicitly apply runtime Compose configuration; no build |
| `make stop ENV=dev` | Stop an Airflow environment; finish active DAG runs first |
| `make down ENV=dev` | Remove environment containers/network, preserve named volumes |
| `make shell ENV=dev` | Open a runtime service shell |
| `make db-start ENV=dev` | Start the existing metadata PostgreSQL container |
| `make db-query ENV=dev SQL_FILE=path.sql` | Run a metadata SQL file with read-only default |
| `make platform-down` | Remove CI containers/network after idle checks; preserve volumes |

Compose-based runtime operations resolve the image from existing Airflow containers
and require local environment settings/secrets. Missing or inconsistent images fail
closed; initial deployment and recovery after `down` use the CI/CD controller. They are administration
commands, not the normal deployment path. `down` can remove container-local login
files; prefer `stop` for routine pauses.

## Compatibility

Existing automation and saved commands continue to work:

| Existing target | Preferred target |
|---|---|
| `check-fast` | `check` |
| `cicd-start`, `cicd-stop`, `cicd-status` | `platform-start`, `platform-stop`, `platform-status` |
| `cicd-install`, `cicd-down` | `platform-install`, `platform-down` |
| `release-status` | `releases` |
| `db-shell`, `metadata` | `db-connect` |
| `ps` | `status` (new command avoids selecting an image) |
| `inspect` | `sales` (new command uses the running scheduler) |

`ps` and `inspect` retain their older Compose behavior for compatibility.
`airflow-init`, `airflow-smoke`, and `airflow-inspect` refer to the **separate
historical smoke stack**, not dev/test/prod. They remain available but are omitted
from the daily menu. See the [runtime guide](airflow-runtime.md) for those exercises.

The root Makefile holds the menu and defaults. `make/quality.mk`,
`make/platform.mk` and `make/advanced.mk` separate checks, CI services and
compatibility/admin operations. `scripts/runtime.py` handles daily inspection.

Use `make image ENV=test` to inspect the selected image, or
`make ui-apply ENV=test` to recreate only the API server with updated configuration.
