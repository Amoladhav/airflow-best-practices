"""One-command Linux/WSL setup. Existing data and credentials are never replaced."""

import argparse
import json
import os
import re
import secrets
import shutil
import socket
import subprocess
import time
from contextlib import redirect_stdout
from pathlib import Path

import setup as controller
from progress import Progress, duration

ROOT = Path(__file__).resolve().parents[2]
Gitea = controller.Gitea
GateError = controller.GateError
REPORTER = None


def write_secret(path, value):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as stream:
        stream.write(value + "\n")


def command(args, capture=False, **kwargs):
    if not capture and REPORTER is not None:
        return REPORTER.run(args, **kwargs)
    result = subprocess.run(
        args,
        check=True,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
        **kwargs,
    )
    return (result.stdout or "").strip()


def wait_for(description, probe, timeout=1800, progress=None):
    started = time.monotonic()
    deadline = started + timeout
    next_update = started
    while time.monotonic() < deadline:
        value = probe()
        if value:
            if REPORTER:
                REPORTER.emit(
                    "OK", f"{description} ({duration(time.monotonic() - started)})"
                )
            return value
        now = time.monotonic()
        if now >= next_update:
            detail = progress() if progress else description
            message = f"{detail} — waiting {duration(now - started)}, limit {duration(timeout)}"
            if REPORTER:
                REPORTER.emit("WAIT", message)
            else:
                print(message, flush=True)
            next_update = now + 15
        time.sleep(5)
    raise GateError(f"Timed out: {description}. Run setup again to resume.")


def parse_token(output):
    candidates = [
        line.strip()
        for line in output.splitlines()
        if re.fullmatch(r"[0-9a-f]{40}", line.strip())
    ]
    if len(candidates) != 1:
        raise GateError("Unexpected token response; no credential was printed")
    return candidates[0]


def main():
    global REPORTER
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default="airflow")
    parser.add_argument("--gitea-port", type=int, default=3000)
    parser.add_argument(
        "--airflow-port", type=int, default=8081, help="First of three UI ports"
    )
    parser.add_argument("--username")
    parser.add_argument("--email")
    args = parser.parse_args()
    REPORTER = Progress(ROOT)
    print("\nAirflow CI/CD Lab — setup", flush=True)
    print(
        f"Project: {args.project} | Gitea: http://localhost:{args.gitea_port}",
        flush=True,
    )
    print(f"Detailed log: {REPORTER.path}\n", flush=True)
    REPORTER.stage("Preflight: Docker, Git and installation identity")
    if not re.fullmatch(r"[a-z][a-z0-9-]{1,35}", args.project):
        raise GateError(
            "Use a lowercase project name with letters, numbers and hyphens"
        )
    ports = [args.gitea_port, *range(args.airflow_port, args.airflow_port + 3)]
    if len(set(ports)) != 4 or any(not 1024 <= p <= 65535 for p in ports):
        raise GateError("Choose four distinct unprivileged ports")
    for tool in ("docker", "git"):
        if not shutil.which(tool):
            raise GateError(f"Install {tool} before running setup")
    command(["docker", "info"], capture=True)
    command(["docker", "compose", "version"], capture=True)
    source = command(["git", "rev-parse", "HEAD"], capture=True, cwd=ROOT)
    # Publish committed application code only. Local configuration is mounted separately.
    dirty = command(
        ["git", "status", "--porcelain", "--untracked-files=no"], capture=True, cwd=ROOT
    )
    if dirty and not (ROOT / "secrets/setup-state.json").exists():
        raise GateError(
            "Commit source changes before setup; only committed code is seeded"
        )
    directory = ROOT / "secrets"
    directory.mkdir(mode=0o700, exist_ok=True)
    state_path = directory / "setup-state.json"
    if state_path.exists():
        state = json.loads(state_path.read_text())
        if (state["project"], state["gitea_port"], state["airflow_port"]) != (
            args.project,
            args.gitea_port,
            args.airflow_port,
        ):
            raise GateError(
                "Setup identity differs from saved state; use a separate checkout"
            )
    else:
        # Refuse to adopt an existing installation implicitly.
        existing = command(
            [
                "docker",
                "ps",
                "-aq",
                "--filter",
                f"label=com.docker.compose.project={args.project}-cicd",
            ],
            capture=True,
        )
        volumes = command(
            [
                "docker",
                "volume",
                "ls",
                "-q",
                "--filter",
                f"label=com.docker.compose.project={args.project}-cicd",
            ],
            capture=True,
        )
        if existing or volumes:
            raise GateError(
                "Existing platform detected without setup state; use normal platform commands, or a separate checkout/project for fresh setup"
            )
        for port in ports:
            with socket.socket() as sock:
                try:
                    sock.bind(("127.0.0.1", port))
                except OSError:
                    raise GateError(f"Port {port} is in use") from None
        username = (
            args.username or input("Administrator username [cicd]: ").strip() or "cicd"
        )
        email = args.email or input("Administrator email: ").strip()
        if (
            not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", username)
            or "@" not in email
        ):
            raise GateError("Invalid administrator username or email")
        state = dict(
            project=args.project,
            gitea_port=args.gitea_port,
            airflow_port=args.airflow_port,
            username=username,
            email=email,
            source=source,
        )
        write_secret(state_path, json.dumps(state))
    source = state["source"]
    username = state["username"]
    env = dict(
        os.environ,
        LAB_PROJECT_PREFIX=args.project,
        GITEA_PORT=str(args.gitea_port),
        PWD=str(ROOT),
    )
    compose = [
        "docker",
        "compose",
        "--project-directory",
        str(ROOT),
        "-f",
        str(ROOT / "infra/docker/compose.cicd.yaml"),
    ]

    def dc(*parts, capture=False):
        return command([*compose, *parts], capture=capture, env=env, cwd=ROOT)

    def admin(*parts):
        return dc(
            "exec",
            "-T",
            "--user",
            "git",
            "gitea",
            "gitea",
            "--config",
            "/data/gitea/conf/app.ini",
            "admin",
            "user",
            *parts,
            capture=True,
        )

    REPORTER.stage("[1/7] Preparing isolated inputs and credentials")
    (ROOT / "environments/platform.env").write_text(
        f"LAB_PROJECT_PREFIX={args.project}\nGITEA_PORT={args.gitea_port}\n"
    )
    for index, target in enumerate(("dev", "test", "prod")):
        path = ROOT / f"data/{target}/input"
        path.mkdir(parents=True, exist_ok=True)
        if not (path / "sales.csv").exists():
            shutil.copyfile(ROOT / "sample_data/sales.csv", path / "sales.csv")
        secret = directory / f"{target}.env"
        if not secret.exists():
            write_secret(secret, "AIRFLOW_JWT_SECRET=" + secrets.token_hex(32))
        config = ROOT / f"environments/{target}.env"
        text = config.read_text()
        text = re.sub(
            r"(?m)^COMPOSE_PROJECT_NAME=.*$",
            f"COMPOSE_PROJECT_NAME={args.project}-{target}",
            text,
        )
        text = re.sub(
            r"(?m)^AIRFLOW_PORT=.*$", f"AIRFLOW_PORT={args.airflow_port + index}", text
        )
        config.write_text(text)
    dc("up", "-d", "--wait", "--wait-timeout", "180", "gitea")
    REPORTER.stage("[2/7] Creating administrator and scoped API credentials")
    users = admin("list")
    if not any(
        re.match(rf"\d+\s+{re.escape(username)}\s+", line.strip())
        for line in users.splitlines()
    ):
        output = admin(
            "create",
            "--username",
            username,
            "--email",
            state["email"],
            "--admin",
            "--random-password",
            "--random-password-length",
            "32",
            "--must-change-password=false",
        )
        write_secret(directory / "gitea-admin-login.txt", output)

    def token(filename, scope):
        path = directory / filename
        if not path.exists():
            value = parse_token(
                admin(
                    "generate-access-token",
                    "--username",
                    username,
                    "--token-name",
                    "lab-" + secrets.token_hex(6),
                    "--scopes",
                    scope,
                    "--raw",
                )
            )
            write_secret(path, value)
        return path.read_text().strip()

    setup_token = token("setup-api-token", "all")
    runtime_token = token("cicd.api-token", "write:repository")
    url = f"http://localhost:{args.gitea_port}"
    app = f"{username}/airflow-cicd-lab"
    control = f"{username}/airflow-cicd-deploy"
    print(f"Application CI: {url}/{app}/actions", flush=True)
    print(f"Deployment:     {url}/{control}/actions", flush=True)
    api = Gitea(url, setup_token, app)
    (ROOT / "environments/cicd.env").write_text(
        f"GITEA_URL=http://gitea:3000\nAPP_REPO={app}\nCONTROL_REPO={control}\nAPI_TOKEN_FILE=/run/secrets/cicd-api-token\nRELEASE_DIR=/releases\n"
    )
    REPORTER.stage("[3/7] Creating repositories and registering scoped runners")
    repos = {item["name"] for item in api.request("/user/repos?limit=50")}
    for name in ("airflow-cicd-lab", "airflow-cicd-deploy"):
        if name not in repos:
            api.request(
                "/user/repos",
                "POST",
                {
                    "name": name,
                    "private": True,
                    "auto_init": name.endswith("deploy"),
                    "default_branch": "main",
                },
            )
        api.request(
            f"/repos/{username}/{name}",
            "PATCH",
            {
                "has_actions": True,
                "allow_fast_forward_only_merge": True,
                "allow_merge_commits": False,
                "allow_rebase": False,
                "allow_rebase_explicit": False,
                "allow_squash_merge": False,
            },
        )
    for repository, filename in (
        (app, "cicd.runner-token"),
        (control, "cicd.deploy-runner-token"),
    ):
        path = directory / filename
        if not path.exists():
            result = api.request(
                f"/repos/{repository}/actions/runners/registration-token", "POST"
            )
            write_secret(path, result["token"])
    if not (directory / "cicd.webhook-secret").exists():
        write_secret(directory / "cicd.webhook-secret", secrets.token_hex(32))
    dc(
        "--profile",
        "ci",
        "--profile",
        "deploy",
        "up",
        "-d",
        "--build",
        "--wait",
        "--wait-timeout",
        "240",
    )

    def runners_ready():
        return all(
            any(
                r.get("status") == "online"
                and not r.get("busy")
                and not r.get("disabled")
                for r in api.request(f"/repos/{repo}/actions/runners").get(
                    "runners", []
                )
            )
            for repo in (app, control)
        )

    wait_for("Waiting for both runners to register", runners_ready, 180)
    REPORTER.stage("[4/7] Publishing controller and configuring signed webhook")
    runtime = Gitea(url, runtime_token, app)
    with redirect_stdout(REPORTER.log):
        controller.install(runtime, control)
    REPORTER.stage("[5/7] Seeding branches and running real dev/test deployment")
    branches = {item["name"] for item in (api.repo("/branches") or [])}
    for branch in ("test", "dev"):
        if branch not in branches:
            runtime.git(
                ["push", f"{url}/{app}.git", f"{source}:refs/heads/{branch}"], ROOT
            )
    api.repo("", "PATCH", {"default_branch": "dev"})

    def verified(target):
        result = subprocess.run(
            [
                *compose,
                "--profile",
                "deploy",
                "exec",
                "-T",
                "deploy-runner",
                "cat",
                f"/releases/{target}.json",
            ],
            env=env,
            capture_output=True,
            text=True,
        )
        if result.returncode:
            return None
        record = json.loads(result.stdout)
        return (
            record
            if record.get("status") == "verified" and record.get("revision") == source
            else None
        )

    seen_links = set()

    def workflow_progress(branch):
        try:
            runs = api.repo("/actions/runs?limit=20").get("workflow_runs", [])
            run = next(
                (
                    r
                    for r in runs
                    if r.get("head_branch") == branch
                    and r.get("head_sha") == source
                    and r.get("event") == "push"
                ),
                None,
            )
            deployments = api.request(f"/repos/{control}/actions/runs?limit=1").get(
                "workflow_runs", []
            )
            for repository, item in (
                (app, run),
                (control, deployments[0] if deployments else None),
            ):
                if item:
                    link = f"{url}/{repository}/actions/runs/{item['id']}"
                    if link not in seen_links:
                        print(f"  Run details: {link}", flush=True)
                        seen_links.add(link)
            ci = (run.get("conclusion") or run.get("status")) if run else "awaiting run"
            deployment = (
                (deployments[0].get("conclusion") or deployments[0].get("status"))
                if deployments
                else "awaiting dispatch"
            )
            return f"{branch} CI: {ci} | latest deployment: {deployment}"
        except GateError:
            return "Workflow status temporarily unavailable; release verification continues"

    def retry_ci(branch):
        runs = api.repo("/actions/runs?limit=50").get("workflow_runs", [])
        matches = [
            r
            for r in runs
            if r.get("head_sha") == source
            and r.get("head_branch") == branch
            and r.get("event") == "push"
        ]
        if matches and matches[0].get("status") in (
            "completed",
            "success",
            "failure",
            "cancelled",
        ):
            api.repo(f"/actions/runs/{matches[0]['id']}/rerun", "POST")

    if not verified("test") and "dev" in branches:
        retry_ci("dev")
    wait_for(
        "Verified TEST release (includes DEV)",
        lambda: verified("test"),
        progress=lambda: workflow_progress("dev"),
    )
    REPORTER.stage("[6/7] Initial production baseline and branch protection")
    if "main" not in branches:
        runtime.git(["push", f"{url}/{app}.git", f"{source}:refs/heads/main"], ROOT)
    elif not verified("prod"):
        retry_ci("main")
    wait_for(
        "Verified PROD release",
        lambda: verified("prod"),
        progress=lambda: workflow_progress("main"),
    )
    rules = {r["rule_name"] for r in (api.repo("/branch_protections") or [])}
    for branch in ("dev", "main"):
        if branch not in rules:
            api.repo(
                "/branch_protections",
                "POST",
                {
                    "rule_name": branch,
                    "enable_push": False,
                    "enable_force_push": False,
                    "enable_status_check": True,
                    "status_check_contexts": ["CI / quality (pull_request)"],
                    "block_admin_merge_override": True,
                },
            )
    remotes = command(["git", "remote"], capture=True, cwd=ROOT).splitlines()
    remote_url = f"{url}/{app}.git"
    if "gitea" not in remotes:
        command(["git", "remote", "add", "gitea", remote_url], cwd=ROOT)
    elif (
        command(["git", "remote", "get-url", "gitea"], capture=True, cwd=ROOT)
        != remote_url
    ):
        raise GateError("Existing gitea remote differs; it was not overwritten")
    REPORTER.stage("[7/7] Release verification and connection details")
    print(
        f"Gitea: {url}\nAirflow: "
        + ", ".join(f"http://localhost:{p}" for p in ports[1:])
    )
    print(
        "Generated administrator login is stored locally in secrets/gitea-admin-login.txt."
    )
    print("Airflow login: admin; use make airflow-password ENV=dev (or test/prod).")
    print("Subsequent releases: feature PR to dev; test to main PR for production.")
    REPORTER.finish()


if __name__ == "__main__":
    try:
        main()
    except (GateError, OSError, subprocess.CalledProcessError) as exc:
        # Do not echo subprocess arguments or captured credential responses.
        message = (
            str(exc)
            if isinstance(exc, GateError)
            else f"Command exited with status {exc.returncode}"
            if isinstance(exc, subprocess.CalledProcessError)
            else f"Filesystem/process error: {exc.strerror or type(exc).__name__}"
        )
        if REPORTER:
            REPORTER.fail(message)
        else:
            print("Setup stopped: " + message)
        raise SystemExit(1) from None
    except KeyboardInterrupt:
        if REPORTER:
            REPORTER.fail("Interrupted; completed setup state is preserved")
        raise SystemExit(130) from None
    finally:
        if REPORTER:
            REPORTER.close()
