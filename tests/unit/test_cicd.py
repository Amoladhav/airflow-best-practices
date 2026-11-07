"""Exercise release authorization and ordering without Docker or a live Gitea."""

import hashlib
import hmac
import importlib
import io
import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
SHA = "a" * 40
IMAGE = "sha256:" + "b" * 64


@pytest.fixture
def modules(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "infra/gitea/deply-repo/scripts"))
    monkeypatch.syspath_prepend(str(ROOT / "infra/cicd"))
    return (
        importlib.import_module("gitea_api"),
        importlib.import_module("webhook_receiver"),
        importlib.import_module("release"),
    )


def valid_run():
    return {
        "id": 17,
        "run_attempt": 1,
        "repository": {"full_name": "cicd/airflow-cicd-lab"},
        "head_branch": "dev",
        "head_sha": SHA,
        "event": "push",
        "path": ".gitea/workflows/ci.yaml",
        "status": "completed",
        "conclusion": "success",
    }


def test_valid_ci(modules):
    api, _, _ = modules
    api.validate_run(valid_run(), "cicd/airflow-cicd-lab", "dev", SHA)


@pytest.mark.parametrize(
    "field,value",
    [
        ("event", "pull_request"),
        ("conclusion", "failure"),
        ("status", "in_progress"),
        ("head_branch", "feature/untrusted"),
        ("head_sha", "c" * 40),
        ("path", ".gitea/workflows/other.yaml"),
        ("repository", {"full_name": "attacker/app"}),
    ],
)
def test_untrusted_ci_rejected(modules, field, value):
    api, _, _ = modules
    with pytest.raises(api.GateError):
        api.validate_run(
            valid_run() | {field: value}, "cicd/airflow-cicd-lab", "dev", SHA
        )


def test_stale_revision_rejected(modules, monkeypatch):
    api, _, _ = modules
    client = api.Gitea("http://unused", "not-a-real-token", "cicd/airflow-cicd-lab")
    monkeypatch.setattr(client, "repo", lambda _: valid_run())
    monkeypatch.setattr(client, "tip", lambda _: "c" * 40)
    with pytest.raises(api.GateError, match="no longer"):
        client.verify_ci("17", "dev", SHA)


def test_signature_and_event_filter(modules):
    _, receiver, _ = modules
    body, secret = b'{"action":"completed"}', b"test-secret"
    signature = hmac.new(secret, body, hashlib.sha256).hexdigest()
    assert receiver.verify_signature(body, signature, secret)
    assert not receiver.verify_signature(body + b" ", signature, secret)
    assert not receiver.verify_signature(body, signature, b"")
    payload = {
        "action": "completed",
        "repository": valid_run()["repository"],
        "workflow_run": valid_run(),
    }
    assert receiver.candidate(payload, "cicd/airflow-cicd-lab") == ("17", "dev", SHA)
    payload["workflow_run"]["head_branch"] = "test"
    assert receiver.candidate(payload, "cicd/airflow-cicd-lab") is None


def test_webhook_dispatch_deduplicated_and_bad_signature_blocked(modules):
    _, receiver, _ = modules
    calls = []
    api = SimpleNamespace(
        repository="cicd/airflow-cicd-lab",
        verify_ci=lambda *args: valid_run(),
        request=lambda *args: calls.append(args),
    )
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE delivered (run_key TEXT PRIMARY KEY)")
    server = SimpleNamespace(
        api=api, secret=b"test", control_repo="cicd/control", db=db
    )
    body = json.dumps(
        {
            "action": "completed",
            "repository": valid_run()["repository"],
            "workflow_run": valid_run(),
        }
    ).encode()
    signature = hmac.new(server.secret, body, hashlib.sha256).hexdigest()
    try:
        for supplied, expected in [("bad", 401), (signature, 202), (signature, 200)]:
            handler = object.__new__(receiver.Handler)
            handler.server, handler.path = server, "/webhook"
            handler.rfile = io.BytesIO(body)
            handler.headers = {
                "Content-Length": str(len(body)),
                "X-Gitea-Signature": supplied,
                "X-Gitea-Event": "workflow_run",
            }
            replies = []
            handler.reply = lambda code, message: replies.append(code)
            handler.do_POST()
            assert replies == [expected]
        assert len(calls) == 1
        assert calls[0][2]["inputs"]["revision"] == SHA
    finally:
        db.close()


@pytest.fixture
def controller(modules, monkeypatch, tmp_path):
    api_module, _, release = modules
    calls = []
    api = SimpleNamespace(
        url="http://unused",
        repository="cicd/app",
        verify_ci=lambda *args: calls.append(("verify", *args)),
        git=lambda args, cwd=None: calls.append(("git", args)) or "",
    )
    monkeypatch.setattr(release, "from_environment", lambda: api)
    monkeypatch.setenv("RELEASE_DIR", str(tmp_path))
    monkeypatch.setattr(
        release.subprocess, "run", lambda *a, **kw: SimpleNamespace(returncode=0)
    )
    monkeypatch.setattr(release, "image_source", lambda *args: None)

    def command(args, cwd, capture=False, env=None):
        calls.append(("command", args))
        return IMAGE

    monkeypatch.setattr(release, "command", command)
    monkeypatch.setattr(
        release, "deploy", lambda target, *args: calls.append(("deploy", target))
    )
    return release, api_module, calls, tmp_path


def test_dev_before_fast_forward_and_test_same_image(controller):
    release, _, calls, directory = controller
    release.release("dev", SHA, "17", "release")
    dev = calls.index(("deploy", "dev"))
    push = calls.index(("git", ["push", "origin", f"{SHA}:refs/heads/test"]))
    test = calls.index(("deploy", "test"))
    assert dev < push < test
    assert json.loads((directory / f"{SHA}.json").read_text())["image"] == IMAGE


def test_failed_dev_blocks_promotion(controller, monkeypatch):
    release, api, calls, _ = controller

    def fail(*args):
        raise api.GateError("dev failed")

    monkeypatch.setattr(release, "deploy", fail)
    with pytest.raises(api.GateError, match="dev failed"):
        release.release("dev", SHA, "17", "release")
    assert not any(c[0] == "git" and c[1][0] == "push" for c in calls)


def test_prod_requires_verified_test(controller):
    release, api, calls, _ = controller
    with pytest.raises(api.GateError, match="successful test"):
        release.release("main", SHA, "18", "release")
    assert not any(c[0] == "deploy" for c in calls)


def test_prod_reuses_recorded_image_without_build(controller):
    release, _, calls, directory = controller
    (directory / f"{SHA}.json").write_text(
        json.dumps(
            {
                "revision": SHA,
                "image": IMAGE,
                "test": {"status": "verified"},
            }
        )
    )
    release.release("main", SHA, "18", "release")
    assert ("deploy", "prod") in calls
    assert not any(c[0] == "command" and "build" in c[1] for c in calls)


def test_rollback_requires_previous_prod_success(controller):
    release, api, _, directory = controller
    with pytest.raises(api.GateError, match="previously verified"):
        release.release("main", SHA, "", "rollback")
    (directory / f"{SHA}.json").write_text(
        json.dumps(
            {
                "revision": SHA,
                "image": IMAGE,
                "test": {"status": "verified"},
                "prod": {"status": "verified"},
            }
        )
    )
    release.release("main", SHA, "", "rollback")
