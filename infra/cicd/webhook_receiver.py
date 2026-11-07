"""Receive signed Gitea CI events; dispatch only verified dev/main releases."""

import hashlib
import hmac
import json
import logging
import os
import sqlite3
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from gitea_api import GateError, from_environment

LOG = logging.getLogger(__name__)
MAX_BODY = 1024 * 1024


def verify_signature(body: bytes, signature: str, secret: bytes) -> bool:
    return bool(secret) and hmac.compare_digest(
        hmac.new(secret, body, hashlib.sha256).hexdigest(), signature
    )


def candidate(payload: dict, repository: str):
    run = payload.get("workflow_run") or {}
    branch = run.get("head_branch", "").removeprefix("refs/heads/")
    if (
        payload.get("action") != "completed"
        or payload.get("repository", {}).get("full_name") != repository
        or run.get("event") != "push"
        or run.get("conclusion") != "success"
        or branch not in {"dev", "main"}
    ):
        return None
    return str(run.get("id", "")), branch, run.get("head_sha", "")


class Receiver(HTTPServer):
    def __init__(self):
        self.api = from_environment()
        self.secret = Path("/run/secrets/cicd-webhook-secret").read_bytes().strip()
        self.control_repo = os.environ.get("CONTROL_REPO", "cicd/airflow-cicd-deploy")
        self.db = sqlite3.connect("/state/deliveries.sqlite")
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS delivered (run_key TEXT PRIMARY KEY)"
        )
        super().__init__(("0.0.0.0", 9000), Handler)


class Handler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(30)

    def reply(self, code: int, message: str):
        body = (message + "\n").encode()
        self.send_response(code)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self.reply(200 if self.path == "/healthz" else 404, "ok")

    def do_POST(self):
        if self.path != "/webhook":
            self.reply(404, "not found")
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= MAX_BODY:
                self.reply(413, "invalid body size")
                return
            body = self.rfile.read(length)
            if not verify_signature(
                body, self.headers.get("X-Gitea-Signature", ""), self.server.secret
            ):
                self.reply(401, "invalid signature")
                return
            if self.headers.get("X-Gitea-Event") != "workflow_run":
                self.reply(202, "ignored event")
                return
            payload = json.loads(body)
            item = candidate(payload, self.server.api.repository)
            if item is None:
                self.reply(202, "ignored run")
                return
            run_id, branch, revision = item
            run = self.server.api.verify_ci(run_id, branch, revision)
            key = f"{run_id}:{run.get('run_attempt', 0)}"
            if self.server.db.execute(
                "SELECT 1 FROM delivered WHERE run_key = ?", (key,)
            ).fetchone():
                self.reply(200, "already dispatched")
                return
            result = self.server.api.request(
                f"/repos/{self.server.control_repo}/actions/workflows/"
                "deploy.yaml/dispatches?return_run_details=true",
                "POST",
                {
                    "ref": "main",
                    "inputs": {
                        "branch": branch,
                        "revision": revision,
                        "ci_run_id": run_id,
                        "operation": "release",
                    },
                },
            )
            with self.server.db:
                self.server.db.execute("INSERT INTO delivered VALUES (?)", (key,))
            LOG.info(
                "Dispatched %s %s from CI run %s (%s)",
                branch,
                revision,
                run_id,
                "run details returned" if result else "accepted",
            )
            self.reply(202, "deployment dispatched")
        except (ValueError, TypeError, AttributeError):
            self.reply(400, "invalid payload")
        except GateError as exc:
            # Non-2xx makes failed verification/delivery visible in Gitea's webhook UI.
            LOG.warning("Delivery blocked: %s", exc)
            self.reply(503, str(exc))

    def log_message(self, format, *args):
        LOG.info("HTTP %s", args[1] if len(args) > 1 else "request")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    Receiver().serve_forever()
