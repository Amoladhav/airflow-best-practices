# Daily commands. Implementation and compatibility targets live in make/.
PYTHON ?= python3
ENV ?= dev
SERVICE ?= airflow-scheduler
SQL_FILE ?=

.DEFAULT_GOAL := check
CICD_COMPOSE = docker compose --project-directory . -f infra/docker/compose.cicd.yaml --profile ci --profile deploy
RUNTIME_COMPOSE = $(PYTHON) scripts/runtime.py compose --env "$(ENV)" --
HADOLINT_IMAGE := hadolint/hadolint:v2.15.1@sha256:32dac94127fd60b7b7e3fbfc65e1383b9b5e25c9bfd7b8536de7a539fe68a12d

.PHONY: help status logs sales db-connect metadata airflow-password image ui-apply
help:
	@printf '%s\n' \
	  'DEVELOP' \
	  '  make check                 Lint, format check and tests (also plain make)' \
	  '  make format                Format Python files' \
	  '' \
	  'CI/CD PLATFORM — Gitea and runners, not the Airflow environments' \
	  '  make platform-bootstrap    Start Gitea and create its first administrator' \
	  '  make platform-start        Start/resume the CI/CD platform' \
	  '  make platform-stop         Check jobs, disable webhook, stop the platform' \
	  '  make platform-status       Show platform containers and recent jobs' \
	  '  make platform-install      Publish trusted controller and install webhook' \
	  '  make releases              Show verified releases and latest attempts' \
	  '' \
	  'AIRFLOW — ENV=dev (default), test or prod; no image digest needed' \
	  '  make ui-apply ENV=test      Apply API/UI settings using the deployed image' \
	  '  make image ENV=test         Show the image selected automatically' \
	  '  make status ENV=prod       Show environment containers' \
	  '  make logs ENV=prod         Follow scheduler logs; SERVICE=... is optional' \
	  '  make sales ENV=prod        Read sales rows from SQLite' \
	  '  make db-connect ENV=prod   SQL prompt labeled [prod]; PostgreSQL metadata' \
	  '  make airflow-password ENV=prod  Show admin UI password locally' \
	  '' \
	  'Promote code through PRs: feature -> dev -> test -> main (prod).' \
	  'Deployment is automated; there is no everyday make deploy command.' \
	  'Advanced operations and old command names: docs/commands.md'

status logs sales db-connect airflow-password image ui-apply:
	@$(PYTHON) scripts/runtime.py $@ --env "$(ENV)" --service "$(SERVICE)"

metadata: db-connect

include make/quality.mk
include make/platform.mk
include make/advanced.mk
