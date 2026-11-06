# Local quality checks

Activate the project virtual environment and install development dependencies:

```bash
python3 -m pip install -e ".[dev]"
```

Run the fast quality gate:

```bash
make check-fast
```

Install the Git hook for this checkout:

```bash
python3 -m pre_commit install
```

Hooks check applicable staged files during commits. Whitespace hooks may modify
files; review and stage those fixes before retrying the commit.
The Dockerfile hook requires Docker to be running.


The gate runs these checks in order and stops at the first failure:

| Stage | Check | Purpose |
|---|---|---|
| Lint | Ruff and SQLFluff | Check Python/Airflow rules and SQLite SQL parsing/style |
| Formatting | Ruff format check | Verify consistent Python formatting |
| Tests | pytest | Run unit and SQLite integration tests |

To apply formatting:

```bash
make format
```

Review resulting changes before committing.

## Earlier verification

On WSL with Python 3.14, Ruff 0.17.3 and pytest 9.2.0:

- The complete gate passed: 20 tests and 25 subtests.
- Removing the blank line between standard-library and application imports
  in `src/sales_lab/load.py` produced Ruff diagnostic I001.
- Make stopped at lint with Error 2; formatting and tests did not run.
- Restoring the import grouping returned the gate to passing.

## AFL-107 verification — 2026-11-05

- `make check-fast` passed Ruff, SQLFluff, Python formatting,
  29 tests and 36 subtests.
- An unused import caused Ruff F401 and blocked a commit; HEAD stayed unchanged.
- File-hygiene hooks corrected whitespace/newlines and passed on rerun.
- SQLFluff parsed SQLite UPSERT and named colon parameters.
  SQL layout and final-newline violations were corrected; CLI and hook passed.
- `make lint-docker` and the Hadolint hook passed using a digest-pinned image.
  Docker is required for this separate check, but not for `make check-fast`.
- These results establish local checks, not Gitea CI or deployment acceptance.

## Scope and limitations

The tests cover transformation, CSV ingestion, initial SQLite loading,
identical replay, existing-record updates, rollback and recovery.

A separate wheel verification confirmed that the installed distribution
contains both SQL resources and passes all 20 tests.

`make check-fast` does not currently build or verify a wheel. It does not
validate Airflow runtime behavior, Spark, hosted CI, deployment or AWS.

Direct development-tool versions are pinned. Transitive dependencies and
build dependencies are not fully locked.
