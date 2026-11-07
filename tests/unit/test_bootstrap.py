"""Bootstrap must preserve existing administrators and fail closed on unknown output."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

spec = importlib.util.spec_from_file_location(
    "bootstrap", Path(__file__).resolve().parents[2] / "infra/cicd/bootstrap.py"
)
bootstrap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bootstrap)


def test_existing_admin_never_prompts_or_creates(monkeypatch):
    calls = []

    def run(args, **kwargs):
        calls.append(args)
        return SimpleNamespace(
            stdout="ID   Username Email IsAdmin\n1 cicd local@example.com true\n"
        )

    monkeypatch.setattr(bootstrap.subprocess, "run", run)
    monkeypatch.setattr("builtins.input", lambda _: pytest.fail("Unexpected prompt"))
    bootstrap.bootstrap()
    assert len(calls) == 2
    assert "create" not in calls[-1]


def test_new_admin_uses_generated_password(monkeypatch):
    calls = []
    answers = iter(["cicd", "local@example.com"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))

    def run(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(stdout="ID   Username Email IsAdmin\n")

    monkeypatch.setattr(bootstrap.subprocess, "run", run)
    bootstrap.bootstrap()
    args, options = calls[-1]
    assert "--random-password" in args
    assert "--password" not in args
    assert "--must-change-password" in args
    assert not options.get("capture_output")


@pytest.mark.parametrize("output", ["", "unexpected response", "database unavailable"])
def test_unknown_list_output_fails_closed(output):
    with pytest.raises(RuntimeError, match="Unrecognized"):
        bootstrap.has_admin(output)
