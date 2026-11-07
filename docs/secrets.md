# Credentials and Airflow login

Credentials stay on the local machine. Git-ignored files are mounted into the
services that need them; application CI does not receive deployment credentials.
Compose file secrets are local file mounts, not an encrypted secret vault.

## Airflow administrator password

Each environment uses Airflow's SimpleAuthManager. The default username is `admin`.
Retrieve its password from the selected environment's running API container:

```bash
make airflow-password ENV=dev
```

```bash
make airflow-password ENV=test
```

```bash
make airflow-password ENV=prod
```

These commands deliberately print the password **in your local terminal**. Do not
paste it into chat, screenshots, issue reports or CI logs. No password is saved to
the repository. The command reads the configured password file, falling back to
`$AIRFLOW_HOME/simple_auth_manager_passwords.json.generated`.

Open the corresponding UI at localhost ports 8081, 8082 or 8083. The generated
password file is container-local in this setup: recreating the API container can
change the login password. Retrieve it again after deployment if login fails.
The JWT secret below is not the UI password. SimpleAuthManager is intended for
local development/testing; the environment named prod is still part of this lab.
See [Airflow SimpleAuthManager](https://airflow.apache.org/docs/apache-airflow/3.3.2/core-concepts/auth-manager/simple/index.html).

## Local secret inventory

| File / credential | Purpose | Used by |
|---|---|---|
| `secrets/dev.env` | Dev execution API JWT signing secret | Dev Airflow services |
| `secrets/test.env` | Test JWT signing secret | Test Airflow services |
| `secrets/prod.env` | Prod JWT signing secret | Prod Airflow services |
| `secrets/cicd.runner-token` | Application repository runner registration | CI runner |
| `secrets/cicd.deploy-runner-token` | Control repository runner registration | Deployment runner |
| `secrets/cicd.api-token` | Gitea repository API/Git access for release automation | Receiver and deployment runner |
| `secrets/cicd.webhook-secret` | Sign/verify CI completion webhooks | Gitea webhook configuration and receiver |
| Generated Airflow password file | Browser login for `admin` | Each API server container |

The two runner tokens come from different repositories. They are not substitutes
for the personal API token. Keep files owner-readable/writable only (`600`).

`python3 infra/cicd/setup.py credentials` prompts for the API token without echoing
it, generates the webhook secret, and preserves existing nonempty files. The API
token needs repository read/write access for the configured app/control repositories;
it does not need site-admin scope. Never add this token to application Actions secrets.
The lab's PostgreSQL account/password are explicitly defined in Compose for local
use and do not supply the Airflow browser login.

## Rotation and backup

- Preserve each environment's JWT secret across routine restarts. Changing it
  requires a coordinated restart of that environment after active work finishes.
- After replacing a local API token, recreate the receiver and deployment runner
  so Docker Desktop refreshes file mounts. Update the webhook with
  `make platform-install` after changing its signing secret.
- Runner registration lives in named volumes. Do not delete registration volumes
  just to refresh a token; a registration token is used to enroll a runner.
- Keep protected backups of local secret files and named state volumes outside
  Git. Neither this project nor Docker Compose encrypts those files at rest.
