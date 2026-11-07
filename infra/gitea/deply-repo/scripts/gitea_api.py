"""Small Gitea client shared by the trusted receiver and release controller."""

import base64
import json
import os
import re
import subprocess
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener


class GateError(RuntimeError):
    """A release prerequisite was not satisfied."""


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Never forward a credential to a server-selected URL.
        return None


class Gitea:
    def __init__(self, url: str, token: str, repository: str):
        if not re.fullmatch(r"[\w.-]+/[\w.-]+", repository):
            raise GateError("Invalid repository name")
        self.url = url.rstrip("/")
        self.token = token
        self.repository = repository

    def request(self, path: str, method: str = "GET", body=None):
        request = Request(
            self.url + "/api/v1" + path,
            data=None if body is None else json.dumps(body).encode(),
            method=method,
            headers={
                "Authorization": "token " + self.token,
                "Content-Type": "application/json",
            },
        )
        try:
            with build_opener(NoRedirect).open(request, timeout=20) as response:
                data = response.read()
                return json.loads(data) if data else None
        except HTTPError as exc:
            raise GateError(f"Gitea {method} {path}: HTTP {exc.code}") from None
        except (URLError, TimeoutError, json.JSONDecodeError):
            raise GateError(f"Gitea {method} {path}: request failed") from None

    def repo(self, suffix: str, method: str = "GET", body=None):
        return self.request(f"/repos/{self.repository}{suffix}", method, body)

    def tip(self, branch: str) -> str:
        if branch not in {"dev", "test", "main"}:
            raise GateError("Unsupported branch")
        return self.repo(f"/branches/{branch}")["commit"]["id"]

    def verify_ci(self, run_id: str, branch: str, revision: str) -> dict:
        if not run_id.isdecimal() or not re.fullmatch(r"[0-9a-f]{40}", revision):
            raise GateError("Expected numeric CI run ID and full commit SHA")
        run = self.repo(f"/actions/runs/{run_id}")
        validate_run(run, self.repository, branch, revision)
        if self.tip(branch) != revision:
            raise GateError(f"Requested revision is no longer the {branch} tip")
        return run

    def git(self, args: list[str], cwd: Path | None = None) -> str:
        # Credential is in a subprocess environment, not argv or a saved Git config.
        auth = base64.b64encode(f"cicd:{self.token}".encode()).decode()
        env = dict(os.environ)
        env.update(
            GIT_TERMINAL_PROMPT="0",
            GIT_CONFIG_COUNT="2",
            GIT_CONFIG_KEY_0=f"http.{self.url}/.extraHeader",
            GIT_CONFIG_VALUE_0="Authorization: Basic " + auth,
            GIT_CONFIG_KEY_1="credential.helper",
            GIT_CONFIG_VALUE_1="",
        )
        result = subprocess.run(
            ["git", *args],
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            timeout=180,
        )
        if result.returncode:
            # Git may print remote content: do not echo it with credentials in scope.
            raise GateError(f"Git {args[0]} failed; check access and branch protection")
        return result.stdout.strip()


def validate_run(run: dict, repository: str, branch: str, revision: str) -> None:
    """Require the actual server-side CI push run, never a PR-supplied result."""
    if branch not in {"dev", "main"}:
        raise GateError("Only dev and main CI can request deployment")
    if (
        run.get("repository", {}).get("full_name") != repository
        or run.get("head_sha") != revision
        or run.get("head_branch") not in {branch, f"refs/heads/{branch}"}
        or run.get("event") != "push"
        or run.get("path", "").split("@", 1)[0] != ".gitea/workflows/ci.yaml"
        or run.get("conclusion") != "success"
        or run.get("status") not in {"completed", "success"}
    ):
        raise GateError(
            "Expected successful CI push run for this repository/branch/SHA"
        )


def from_environment() -> Gitea:
    return Gitea(
        os.environ.get("GITEA_URL", "http://gitea:3000"),
        Path(os.environ.get("API_TOKEN_FILE", "/run/secrets/cicd-api-token"))
        .read_text()
        .strip(),
        os.environ.get("APP_REPO", "cicd/airflow-cicd-lab"),
    )
