"""Owner-run setup: local secrets, trusted workflow publication and webhook wiring."""

import argparse
import getpass
import json
import os
import secrets
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONTROL = ROOT / "infra/gitea/deply-repo"
sys.path.insert(0, str(CONTROL / "scripts"))
from gitea_api import GateError, Gitea  # noqa: E402

HOOK_URL = "http://webhook-receiver:9000/webhook"


def configuration() -> dict:
    return dict(
        line.split("=", 1)
        for line in (ROOT / "environments/cicd.env").read_text().splitlines()
        if line and not line.startswith("#")
    )


def secret_file(name: str, value: str) -> None:
    path = ROOT / name
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as stream:
        stream.write(value + "\n")


def credentials() -> None:
    token = ROOT / ".env.cicd.api-token"
    if not token.exists():
        value = getpass.getpass(
            "Gitea API token (repository read/write scope): "
        ).strip()
        if not value:
            raise GateError("Empty token; no file written")
        secret_file(token.name, value)
    if not (ROOT / ".env.cicd.webhook-secret").exists():
        secret_file(".env.cicd.webhook-secret", secrets.token_hex(32))
    for name in (".env.cicd.api-token", ".env.cicd.webhook-secret"):
        path = ROOT / name
        if not path.read_text().strip():
            raise GateError(f"{name} is empty")
        path.chmod(0o600)
    print("Local secrets ready; no credentials were printed.")


def hook(api: Gitea, active: bool) -> None:
    hooks = api.repo("/hooks?limit=50")
    existing = [h for h in hooks if h.get("config", {}).get("url") == HOOK_URL]
    if len(existing) > 1:
        raise GateError("Duplicate deployment hooks exist; keep one before continuing")
    body = {
        "type": "gitea",
        "active": active,
        "events": ["workflow_run"],
        "config": {
            "url": HOOK_URL,
            "content_type": "json",
            "http_method": "POST",
            "secret": (ROOT / ".env.cicd.webhook-secret").read_text().strip(),
        },
    }
    if existing:
        api.repo(f"/hooks/{existing[0]['id']}", "PATCH", body)
    elif active:
        api.repo("/hooks", "POST", body)
    print("Deployment webhook " + ("enabled" if active else "disabled"))


def install(api: Gitea, control_repo: str) -> None:
    # Deliberately publish only reviewed infrastructure templates, never the worktree.
    with tempfile.TemporaryDirectory(prefix="airflow-control-") as temp:
        checkout = Path(temp) / "control"
        api.git(
            [
                "clone",
                "--branch",
                "main",
                f"{api.url}/{control_repo}.git",
                str(checkout),
            ]
        )
        files = [
            CONTROL / ".gitea/workflows/deploy.yaml",
            *sorted((CONTROL / "scripts").glob("*.py")),
            CONTROL / "scripts/deploy.sh",
        ]
        for source in files:
            target = checkout / source.relative_to(CONTROL)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        paths = [str(p.relative_to(CONTROL)) for p in files]
        api.git(["add", "--", *paths], checkout)
        if api.git(["diff", "--cached", "--name-only"], checkout):
            api.git(
                [
                    "-c",
                    "user.name=Airflow lab setup",
                    "-c",
                    "user.email=airflow-lab@localhost",
                    "commit",
                    "-m",
                    "Install reviewed deployment controller",
                ],
                checkout,
            )
            api.git(["push", "origin", "HEAD:main"], checkout)
        print(
            "Deployment controller installed at "
            + api.git(["rev-parse", "HEAD"], checkout)
        )
    hook(api, True)


def require_idle(api: Gitea, repositories: list[str]) -> None:
    busy = []
    for repository in repositories:
        page = 1
        while True:
            result = api.request(
                f"/repos/{repository}/actions/runs?limit=50&page={page}"
            )
            runs = result.get("workflow_runs", [])
            for run in runs:
                if run.get("status") not in {
                    "completed",
                    "success",
                    "failure",
                    "cancelled",
                    "skipped",
                    "timed_out",
                }:
                    busy.append(f"{repository} run {run['id']}: {run.get('status')}")
            if len(runs) < 50:
                break
            page += 1
    if busy:
        raise GateError("Finish/cancel these jobs before stopping:\n" + "\n".join(busy))
    print("No queued or active CI/deployment runs.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", choices=["credentials", "install", "resume", "pause", "status"]
    )
    parser.add_argument("--url", default="http://localhost:3000")
    args = parser.parse_args()
    try:
        if args.action == "credentials":
            credentials()
            return
        config = configuration()
        api = Gitea(
            args.url,
            (ROOT / ".env.cicd.api-token").read_text().strip(),
            config["APP_REPO"],
        )
        if args.action == "install":
            install(api, config["CONTROL_REPO"])
        elif args.action == "resume":
            hook(api, True)
        elif args.action == "pause":
            require_idle(api, [config["APP_REPO"], config["CONTROL_REPO"]])
            hook(api, False)
            require_idle(api, [config["APP_REPO"], config["CONTROL_REPO"]])
        else:
            for repo in (config["APP_REPO"], config["CONTROL_REPO"]):
                runs = api.request(f"/repos/{repo}/actions/runs?limit=5").get(
                    "workflow_runs", []
                )
                print(
                    json.dumps(
                        [
                            {
                                "repo": repo,
                                "id": r["id"],
                                "branch": r.get("head_branch"),
                                "sha": r.get("head_sha"),
                                "status": r.get("status"),
                                "conclusion": r.get("conclusion"),
                            }
                            for r in runs
                        ],
                        indent=2,
                    )
                )
    except (GateError, OSError) as exc:
        raise SystemExit(str(exc)) from None


if __name__ == "__main__":
    main()
