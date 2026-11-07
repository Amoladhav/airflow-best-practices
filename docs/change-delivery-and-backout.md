# Release promotion and backout

The release source is a Git commit; the deployed artifact is an immutable local
Docker image ID. A branch update alone is not proof that an environment is running
that release. Inspect both the deployment workflow and `make releases`.

## Promotion

1. Open a feature PR with base `dev`; review checks and fast-forward merge manually.
2. Successful dev push CI dispatches the trusted deployment workflow.
3. The controller builds/reuses the image, deploys dev and verifies a scheduler run.
4. It fast-forwards `test`, deploys the same image and verifies test.
5. Open a PR with base `main`, compare `test`; review CI and fast-forward merge manually.
6. Successful main push CI deploys the recorded test image to prod without rebuilding.

A failed dev check prevents test promotion. A failed test deployment leaves its
branch advanced but without a successful release record; prod refuses that release.
Do not use squash/merge commits for environment promotion: the accepted source SHA
must remain the one associated with the tested artifact.

## Inspect a failed attempt

```bash
make releases
```

```bash
make status ENV=prod
```

```bash
make logs ENV=prod
```

Release records contain the last verified state and a separate latest attempt.
An interrupted attempt can remain `deploying`; inspect the actual containers and
DAG runs before retrying. Stop manual DAG triggers and input edits during rollout.

## Retry

In the private control repository, choose **Actions → Deployment → Run workflow**
on `main`. Supply `operation=release`, the accepted application branch (`dev` or
`main`), its full commit SHA and a successful application **push CI run ID**.
The controller checks the current branch tip and CI result again. A stale revision
is rejected. A missing production image is not rebuilt during promotion.

## Production backout

Choose **Deployment → Run workflow** on control `main`, with:

| Input | Value |
|---|---|
| `operation` | `rollback` |
| `branch` | `main` |
| `revision` | Full SHA of a previously verified production release |
| `ci_run_id` | Empty |

The controller requires the retained release record and image, redeploys that
artifact, and reruns verification. This operation changes runtime code only. It
does not move Git branches, reverse database migrations, or undo business data.
Follow a runtime backout with a reviewed source correction/revert through the
normal delivery flow. Preserve release images and state volumes.

See [architecture](architecture.md), [setup](local-cicd.md) and
[credentials](secrets.md) for component boundaries and operating instructions.
