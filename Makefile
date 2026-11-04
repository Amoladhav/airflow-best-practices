PYTHON ?= python3

.PHONY: check-fast lint format-check test format fix

check-fast:
	$(MAKE) lint
	$(MAKE) format-check
	$(MAKE) test

lint:
	$(PYTHON) -m ruff check .

format-check:
	$(PYTHON) -m ruff format --check .

test:
	$(PYTHON) -I -m pytest -q

format:
	$(PYTHON) -m ruff format .

fix:
	$(PYTHON) -m ruff check . --fix