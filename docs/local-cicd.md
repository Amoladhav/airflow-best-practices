# Local release automation

This lab uses Gitea for source control and two repository-scoped runners. The
application runner has its own disposable Docker engine. The deployment runner
has host Docker access and accepts jobs only from the private control repository.
All control code is maintained here under `infra/gitea/deply-repo/` (the existing
folder spelling is retained). `make cicd-install` publishes those files into the
control repository; no web-editor copying is required.

## Flow

```text
Feature PR → CI → owner fast-forward merge to dev
  → dev push CI succeeds → signed webhook → trusted deployment workflow
  → build/reuse commit image → import check → deploy dev → scheduler/data check
  → fast-forward test branch → deploy same image to test → scheduler/data check
  → owner fast-forward merge test into main → main push CI succeeds
  → deploy recorded test image to prod → scheduler/data check
```

The test branch advances after dev succeeds. If the test deployment fails, its
branch has advanced but its release is NOT verified. Prod refuses that revision.
Test push CI runs as an additional check; it does not start another deployment.
Prod requires both successful main CI and the matching successful test deployment.
No process automatically merges into dev or main. Use fast-forward merges so the
same SHA identifies the tested artifact. Do not squash or create merge commits
for environment promotion. Protect dev/main from direct and force pushes and
require the `CI / quality` check; verify the exact status name in your Gitea UI.
Test must allow the automation identity to push fast-forward updates.

## Five setup and acceptance steps

Existing prerequisites: Gitea and the two repository-scoped runners registered;
application repository has dev/test/main; control repository is private with main;
Airflow environment files, secrets and three input directories exist as described
in [airflow-runtime.md](airflow-runtime.md). This sequence builds on those confirmed
lab prerequisites, not on a fresh empty computer. No volumes are deleted.

1. In Gitea **user Settings → Applications**, generate a local automation API token
   with **repository: Read and Write** (`write:repository`), no admin scope. This
   token belongs to an identity able to read the app, fast-forward test, publish
   the control workflow and configure the app webhook. In this single-owner lab
   that is `cicd`. Run the hidden prompt below; never put the token in CI secrets:

   ```bash
   python3 infra/cicd/setup.py credentials
   ```

   The command stores the API token and a generated webhook signing secret in
   ignored `.env.cicd.*` files with mode 600. It never prints either secret.
   Adjust public repository names in `environments/cicd.env` for another owner.

2. Start/rebuild infrastructure, then install the reviewed controller and webhook:

   ```bash
   make cicd-start
   ```

   ```bash
   make cicd-install
   ```

   `cicd-install` clones the control repository into a temporary directory, commits
   and pushes only the workflow and scripts, and creates/updates one signed
   `workflow_run` webhook. This is an owner-run publishing operation. The receiver
   is reachable only on the Compose network, at
   `http://webhook-receiver:9000/webhook`; there is no host port or Docker socket.
   Gitea's allowed webhook host is limited to `webhook-receiver`.
   The workflow uses a local API-token file and performs its own CI verification.

3. Run `make check-fast`, review the diff, commit these infrastructure files on
   the feature branch and push it to Gitea. Do not stage private context, secrets,
   `AGENTS.md`, or unrelated owner edits. Open the feature → dev PR, wait for CI,
   and manually **fast-forward merge**. A passing dev push CI should automatically
   start **Deployment** in the control repository. No manual dispatch is needed.

4. Wait for Deployment success. Inspect both DAG runs and release records:

   ```bash
   make release-status
   ```

   Dev (`http://localhost:8081`) and test (`http://localhost:8082`) must show the
   successful `sales_etl` run. The records must show the same source SHA and image
   ID, and the `test` Git branch must point to that SHA. Check the test push CI too.

5. Open test → main PR, wait for CI and manually **fast-forward merge**. The main
   push CI triggers prod automatically, using the recorded image without a rebuild.
   Verify `http://localhost:8083`, Deployment success and `make release-status`.
   Only then is end-to-end automatic delivery accepted. Begin the two business
   changes after that: daily reporting, then customer totals with a deliberate
   blocked defect and recovery.

## What is checked

The receiver verifies HMAC-SHA256 over the raw webhook body, then requests the run
from Gitea. Only successful **push** CI runs from the configured app repository,
`.gitea/workflows/ci.yaml`, and current dev/main SHA are eligible. PRs, other
workflows, failed runs and stale revisions cannot deploy. Inputs enter the workflow
through environment variables and are validated before Git or Docker operations.
The receiver stores dispatched run/attempt IDs in a named volume to suppress
normal webhook redelivery. A crash between dispatch and recording can produce a
repeat request; the controller serializes jobs, reuses the image and verifies again.

The controller has no PR runner registration. Its local API credential never enters
application CI jobs. This is still a trusted single-owner Docker lab: accepted
application code and control-repository writers can execute code with deployment
privileges. The repository API scope is broad; do not expose this setup publicly.
The receiver uses the Python standard library HTTP server on an internal network.
Runner APK dependencies and the receiver base image are not fully locked.

The application image contains code, SQL, DAGs and scripts. Environment settings,
input CSV files and named state volumes stay separate. The release image ID and
source label must match the deployed containers. Scheduler-driven `sales_etl`
must finish successfully, including its downstream persisted-row check.
Do not edit input files or manually trigger DAG runs during deployment. The active
run check prevents interrupting existing work but is not a distributed admission
lock against concurrent external triggers. This lab DAG is unscheduled.

## Records and recovery

The `release-data` volume stores `<sha>.json`, last verified `dev.json`, `test.json`,
`prod.json`, and separate `*-attempt.json` files. A failed or interrupted attempt
must not be mistaken for the last verified deployment. A killed process can leave
an attempt marked `deploying`; inspect containers and active DAG runs before retry.
Images and environment data are retained. Do not prune images or remove volumes.

Failed webhook dispatch appears under the application repository's **Settings →
Webhooks → delivery history**, and in receiver logs. Fix the cause, then redeliver.
A previously dispatched but failed deployment is retried with **Deployment → Run
workflow**, supplying `operation=release`, branch, full SHA and successful app CI
run ID. The branch tip and CI result are checked again. Rerunning CI also creates
a new run/attempt notification. No failed deployment advances to a later stage.

For production backout, use **Deployment → Run workflow** on control `main`:
`operation=rollback`, `branch=main`, and a full SHA previously verified in prod.
Leave CI run ID empty. This redeploys the retained image and reruns verification;
it does not move Git branches, reverse metadata migrations, or undo business data.
A missing retained image blocks backout rather than rebuilding it. Follow a runtime
backout with a reviewed source correction/revert through the normal flow.

## Stop and resume

Stop creating PRs/merges/pushes and finish or cancel active CI/deployment jobs first:

```bash
make cicd-stop
```

The command checks both repositories for queued/running jobs, disables the webhook,
checks again, then stops receiver and runners before Gitea. It refuses to stop if
jobs remain. Airflow stays running, and all named volumes/images are retained.
`make cicd-start` resumes the webhook. If work arrived while the hook was disabled,
rerun the relevant CI or manually dispatch after checking its SHA; there is no
background polling or automatic replay of events missed while stopped.

## Evidence

Owner verified: CI, packaged-image import, manual workflow-driven dev deployment,
identical-image test deployment, and scheduler/data checks in both environments.
The new receiver, branch promotion, production path and rollback have local tests;
installation and live acceptance of those additions are still pending.

References: [Gitea webhook signatures/events](https://docs.gitea.com/usage/repository/webhooks/),
[run API](https://docs.gitea.com/api/operations/get-workflow-run/),
[workflow dispatch](https://docs.gitea.com/api/operations/actions-dispatch-workflow/).
