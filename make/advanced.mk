# Compatibility and explicit runtime administration; see docs/commands.md.
.PHONY: airflow-init airflow-smoke airflow-inspect runtime-check config up stop down ps shell db-start db-shell db-query inspect
.PHONY: cicd-start cicd-install cicd-status cicd-stop cicd-down release-status

cicd-start: platform-start
cicd-install: platform-install
cicd-status: platform-status
cicd-stop: platform-stop
cicd-down: platform-down
release-status: releases
db-shell: metadata

airflow-init:
	docker compose --project-directory . -f infra/docker/compose.yaml run --rm airflow-smoke airflow db migrate

airflow-smoke:
	docker compose --project-directory . -f infra/docker/compose.yaml run --rm airflow-smoke airflow dags test sales_etl

airflow-inspect:
	docker compose --project-directory . -f infra/docker/compose.yaml run --rm airflow-smoke python /opt/airflow/scripts/inspect_sales.py

runtime-check:
	@case "$(ENV)" in dev|test|prod) ;; *) printf '%s\n' 'ENV must be dev, test or prod' >&2; exit 2;; esac
	@test -f "environments/$(ENV).env" || { printf '%s\n' 'Missing public environment file' >&2; exit 2; }
	@test -f "secrets/$(ENV).env" || { printf '%s\n' 'Missing environment secrets file; see docs/airflow-runtime.md' >&2; exit 2; }

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

shell: runtime-check
	$(RUNTIME_COMPOSE) exec "$(SERVICE)" bash

db-start: runtime-check
	$(RUNTIME_COMPOSE) start postgres

db-query: runtime-check
	@test -n "$(SQL_FILE)" && test -f "$(SQL_FILE)" || { printf '%s\n' 'Set SQL_FILE to an existing local SQL file' >&2; exit 2; }
	$(RUNTIME_COMPOSE) exec -T -e PGOPTIONS='-c default_transaction_read_only=on' postgres psql -X -v ON_ERROR_STOP=1 -U airflow -d airflow -f - < "$(SQL_FILE)"

inspect: runtime-check
	$(RUNTIME_COMPOSE) run --rm --no-deps airflow-init python /opt/airflow/scripts/inspect_sales.py
