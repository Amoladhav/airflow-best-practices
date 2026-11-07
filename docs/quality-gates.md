# Quality gates

Install development dependencies and the commit hook:

```bash
python3 -m pip install -e '.[dev]'
```

```bash
python3 -m pre_commit install
```

Run the checks used by application CI:

```bash
make check
```

| Stage | Tools | Checks |
|---|---|---|
| Lint | Ruff, SQLFluff | Python/Airflow rules and SQLite SQL style |
| Format | Ruff | Python formatting |
| Test | pytest | Business logic, SQLite integration, release guards and command routing |

The gate stops at the first failure. `make format` applies Python formatting;
review changes before committing. `make check-fast` is a compatibility alias.

Pre-commit also checks file hygiene, YAML/TOML syntax, merge markers, large files
and private-key patterns. Applicable hooks run against staged files. Hooks may fix
whitespace; review and stage those changes before retrying. The application
infra/docker/Dockerfile hook requires Docker and runs the pinned Hadolint image.

```bash
make lint-docker
```

Unit tests and mocked infrastructure checks do not prove a live deployment. The
release workflow separately imports the packaged DAG, verifies running container
image IDs, triggers `sales_etl` through the scheduler and requires successful
persisted-data validation. Direct development dependencies are pinned; transitive
and build dependencies are not fully locked.
