# Gitea, runners and webhook lifecycle. Airflow is managed by release workflows.
.PHONY: platform-start platform-install platform-status platform-stop platform-down releases

platform-start:
	@test -s secrets/cicd.runner-token || { echo 'Missing runner token file'; exit 1; }
	@test -s secrets/cicd.deploy-runner-token || { echo 'Missing deployment runner token file'; exit 1; }
	@test -s secrets/cicd.api-token && test -s secrets/cicd.webhook-secret || { echo 'Run python3 infra/cicd/setup.py credentials'; exit 1; }
	$(CICD_COMPOSE) config --quiet
	$(CICD_COMPOSE) up -d --build --wait --wait-timeout 180
	$(PYTHON) infra/cicd/setup.py resume

platform-install:
	$(PYTHON) infra/cicd/setup.py install

platform-status:
	$(CICD_COMPOSE) ps -a
	$(PYTHON) infra/cicd/setup.py status

releases:
	$(CICD_COMPOSE) exec -T deploy-runner sh -c 'for f in /releases/dev.json /releases/test.json /releases/prod.json /releases/*-attempt.json; do if test -f "$$f"; then echo "$$f"; cat "$$f"; fi; done'

platform-stop:
	$(PYTHON) infra/cicd/setup.py pause
	$(CICD_COMPOSE) stop webhook-receiver runner deploy-runner
	$(CICD_COMPOSE) stop gitea
	$(CICD_COMPOSE) ps -a

platform-down:
	$(PYTHON) infra/cicd/setup.py pause
	$(CICD_COMPOSE) down

.PHONY: platform-bootstrap
platform-bootstrap:
	$(PYTHON) infra/cicd/bootstrap.py
