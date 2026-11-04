PYTHON ?= python3

.PHONY: check-fast lint format-check test format fix airflow-init airflow-smoke airflow-inspect

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

airflow-init:
	docker compose run --rm airflow-smoke airflow db migrate

airflow-smoke:
	docker compose run --rm airflow-smoke airflow dags test sales_etl

airflow-inspect:
	docker compose run --rm airflow-smoke python /opt/airflow/scripts/inspect_sales.py