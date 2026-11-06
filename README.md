# Airflow CI/CD Lab

A local data engineering project exploring how tested code moves through
development, test and production environments. A small sales pipeline provides
the workload; Gitea Actions provides the automated quality checks.

**Current milestone:** push and pull-request CI runs pass on a local Gitea runner.
Automated deployment, release promotion and backout are the next milestones.

## Delivery model

```text
Feature branch → pull request → CI checks → dev → test → main (prod)
```

The intended release process promotes the same identified artifact through each
environment while preserving its data. Today, Airflow environments have separate
runtime state and storage but still share workspace DAGs/scripts and an application
image tag. Branch movement alone does not yet deploy a release.

| Capability | Status |
|---|---|
| CSV validation and transactional SQLite UPSERT | Implemented and tested |
| Replay, updates and rollback behavior | Verified by tests and local runtime checks |
| Airflow dev/test/prod runtime and data isolation | Locally verified |
| Python/Airflow, SQL, file-hygiene and Dockerfile checks | Locally verified |
| Gitea push and pull-request CI | Verified |
| Required-check merge enforcement | Acceptance pending |
| Automated deployment, promotion and backout | Planned |

## Pipeline

`sales_etl` is a manually triggered Airflow DAG:

```text
Sales CSV → validate records → transactional UPSERT → verify stored rows
```

Amounts are stored as integer cents. Invalid records or duplicate IDs within a
batch fail validation. Replaying a batch does not duplicate sales; changed values
update existing IDs. Records omitted from a later batch remain stored.

Business logic lives in `src/sales_lab/`; orchestration lives in `dags/`.
SQLite stores sales, while PostgreSQL stores Airflow metadata.

## Run the local checks

Use Python 3.11+ for development tools; the verified local environment uses Python
3.14. Airflow runs separately in a pinned Airflow 3.3.2 / Python 3.12 image.
Docker with Compose is required for Airflow, Gitea and the Hadolint check.

From the repository root on Linux or WSL:

```bash
python3 -m venv .venv
```

```bash
source .venv/bin/activate
```

```bash
python3 -m pip install -e '.[dev]'
```

```bash
python3 -m pre_commit install
```

```bash
make check-fast
```

The fast gate runs Ruff, SQLFluff, Python formatting checks and unit/SQLite
integration tests. Run the separate Dockerfile check with `make lint-docker`.
See [quality gates](docs/quality-gates.md) for behavior and evidence limits.

## Airflow and CI platform

Follow the [Airflow runtime guide](docs/airflow-runtime.md) to initialize images,
environment settings, secrets and data before using `make up ENV=dev`.
Use `make help` for inspection, logs and shutdown commands.

The local CI platform uses Gitea, a repository-scoped runner and a separate
Docker-in-Docker engine. Its workflow installs development dependencies and runs
`make check-fast` against the submitted code. It does not yet run every local hook
or deploy Airflow. Publishing this repository to GitHub does not enable GitHub
Actions; the workflow currently lives in `.gitea/workflows/`.

Initial Gitea account/repository setup and runner-token provisioning are currently
manual. Once configured, use `make cicd-start`, `make cicd-status` and
`make cicd-stop`. Before stopping, prevent new workflow runs and finish or cancel
queued/running jobs. The stop target stops services; job-state verification remains
an operator step. Named volumes retain repository, registration and cached images.

This is a local learning environment, with lab credentials and a privileged
Docker-in-Docker service. It is not a hardened public hosting configuration.
Keep local secrets and runtime data out of Git.

## Next milestones

1. Verify protected-branch enforcement and owner-authorized integration.
2. Build an identified release and deploy it automatically to dev.
3. Promote that artifact through test and prod; verify runtime identity and data preservation.
4. Exercise failed-deployment recovery and retained-artifact backout.

See [delivery and backout design](docs/change-delivery-and-backout.md) for the
planned contracts. AWS validation follows local delivery acceptance.
