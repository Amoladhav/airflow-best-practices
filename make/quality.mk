# Local checks; used by CI as well as developers.
.PHONY: check check-fast lint format-check test format fix lint-docker

check-fast: check

check:
	$(MAKE) lint
	$(MAKE) format-check
	$(MAKE) test

lint-docker:
	docker run --rm -i $(HADOLINT_IMAGE) < infra/docker/Dockerfile

lint:
	$(PYTHON) -m ruff check .
	$(PYTHON) -m sqlfluff lint src/sales_lab/sql

format-check:
	$(PYTHON) -m ruff format --check .

test:
	$(PYTHON) -I -m pytest -q

format:
	$(PYTHON) -m ruff format .

fix:
	$(PYTHON) -m ruff check . --fix
