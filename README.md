# Airflow CI/CD Lab

A local data engineering project exploring how tested code moves through
development, test and production environments. A small sales pipeline provides
the workload; Gitea Actions provides the automated quality checks.

**Current milestone:** Gitea CI and workflow-driven deployment of the same image
to dev and test are verified. Automatic triggering, branch promotion and the prod
path are implemented; live acceptance is pending.

## Delivery model

```text
Feature branch → pull request → CI checks → dev → test → main (prod)
```

The release process builds an image containing application code, SQL, DAGs and
scripts. It promotes that image through isolated environments while preserving
their data. Owners merge into dev and main; automation verifies CI, deploys dev,
fast-forwards test, and deploys the tested artifact. See the
[five-step setup and acceptance guide](docs/local-cicd.md).

| Capability | Status |
|---|---|
| CSV validation and transactional SQLite UPSERT | Implemented and tested |
| Replay, updates and rollback behavior | Verified by tests and local runtime checks |
| Airflow dev/test/prod runtime and data isolation | Locally verified |
| Python/Airflow, SQL, file-hygiene and Dockerfile checks | Locally verified |
| Gitea push and pull-request CI | Verified |
| Required-check merge enforcement | Acceptance pending |
| Workflow-driven dev/test deployment and DAG verification | Owner verified |
| Automatic triggering, Git promotion, prod and retained-image backout | Implemented; live acceptance pending |

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
or access the Airflow host. A separate trusted deployment runner manages Airflow.
Publishing this repository to GitHub does not enable GitHub
Actions; the workflow currently lives in `.gitea/workflows/`.

Initial Gitea account/repository setup and runner-token provisioning are currently
manual. Once configured, use `make cicd-start`, `make cicd-status` and
`make cicd-stop`. Before stopping, prevent new workflow runs and finish or cancel
queued/running jobs. The stop target checks job state and disables the deployment
webhook before stopping services. Named volumes retain repositories, registration,
release records and cached images. Airflow remains running.

This is a local learning environment, with lab credentials and a privileged
Docker-in-Docker service. It is not a hardened public hosting configuration.
Keep local secrets and runtime data out of Git.

## Next milestones

1. Verify protected-branch enforcement and owner-authorized integration.
2. Accept automatic dev/test delivery and manually authorized prod promotion.
3. Exercise two business changes, a blocked defect and retained-artifact backout.

See [delivery and backout design](docs/change-delivery-and-backout.md) for the
planned contracts. AWS validation follows local delivery acceptance.
