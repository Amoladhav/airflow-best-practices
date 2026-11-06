PYTHON ?= python3

ENV ?= dev
SERVICE ?= airflow-scheduler
SQL_FILE ?=
RUNTIME_COMPOSE = docker compose --project-name airflow-$(ENV) --env-file environments/$(ENV).env --env-file environments/.env.$(ENV).secrets -f compose.runtime.yaml

.PHONY: check-fast lint format-check test format fix airflow-init airflow-smoke airflow-inspect
.PHONY: help runtime-check config up stop down ps logs shell db-shell db-start db-query inspect

check-fast:
	$(MAKE) lint
	$(MAKE) format-check
	$(MAKE) test

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

airflow-init:
	docker compose run --rm airflow-smoke airflow db migrate

airflow-smoke:
	docker compose run --rm airflow-smoke airflow dags test sales_etl

airflow-inspect:
	docker compose run --rm airflow-smoke python /opt/airflow/scripts/inspect_sales.py

help:
	@printf '%s\n' \
	  'Scheduler environments: ENV=dev (default), test, prod' \
	  '  make config ENV=dev             Validate configuration without printing secrets' \
	  '  make up ENV=dev                 Start/apply configuration; do not rebuild images' \
	  '  make stop ENV=dev               Stop services; retain containers and volumes' \
	  '  make down ENV=dev               Remove containers/network; retain named volumes' \
	  '  make ps ENV=dev                 Show all environment containers' \
	  '  make logs ENV=dev               Follow recent logs (SERVICE=airflow-scheduler)' \
	  '  make shell ENV=dev              Open bash (SERVICE=airflow-scheduler)' \
	  '  make db-shell ENV=dev           Open PostgreSQL metadata psql; read-only default' \
	  '  make db-query ENV=dev SQL_FILE=path.sql  Run a local SQL file against metadata' \
	  '  make inspect ENV=dev            Read persisted SQLite sales output' \
	  'Existing airflow-init/airflow-smoke/airflow-inspect targets use the separate smoke stack.' \
	  '  make db-start ENV=dev           Start the existing PostgreSQL container only'

runtime-check:
	@case "$(ENV)" in dev|test|prod) ;; *) printf '%s\n' 'ENV must be dev, test or prod' >&2; exit 2;; esac
	@test -f "environments/$(ENV).env" || { printf '%s\n' 'Missing public environment file' >&2; exit 2; }
	@test -f "environments/.env.$(ENV).secrets" || { printf '%s\n' 'Missing environment secrets file; see docs/airflow-runtime.md' >&2; exit 2; }

config: runtime-check
	$(RUNTIME_COMPOSE) config --quiet

up: runtime-check
	$(RUNTIME_COMPOSE) up -d --no-build

stop: runtime-check
	$(RUNTIME_COMPOSE) stop

down: runtime-check
	$(RUNTIME_COMPOSE) down

ps: runtime-check
	$(RUNTIME_COMPOSE) ps -a

logs: runtime-check
	$(RUNTIME_COMPOSE) logs --follow --tail 100 "$(SERVICE)"

shell: runtime-check
	$(RUNTIME_COMPOSE) exec "$(SERVICE)" bash

db-start: runtime-check
	$(RUNTIME_COMPOSE) start postgres

db-shell: runtime-check
	$(RUNTIME_COMPOSE) exec -e PGOPTIONS='-c default_transaction_read_only=on' postgres psql -X -U airflow -d airflow

db-query: runtime-check
	@test -n "$(SQL_FILE)" && test -f "$(SQL_FILE)" || { printf '%s\n' 'Set SQL_FILE to an existing local SQL file' >&2; exit 2; }
	$(RUNTIME_COMPOSE) exec -T -e PGOPTIONS='-c default_transaction_read_only=on' postgres psql -X -v ON_ERROR_STOP=1 -U airflow -d airflow -f - < "$(SQL_FILE)"

inspect: runtime-check
	$(RUNTIME_COMPOSE) run --rm --no-deps airflow-init python /opt/airflow/scripts/inspect_sales.py
