"""Keep daily inspection scoped to the requested environment and read-only tools."""

import importlib.util
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

SPEC = importlib.util.spec_from_file_location(
    "runtime_commands", Path(__file__).resolve().parents[2] / "scripts/runtime.py"
)
runtime = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runtime)


@pytest.mark.parametrize("environment", ["dev", "test", "prod"])
@pytest.mark.parametrize(
    "action,service",
    [
        ("sales", "airflow-scheduler"),
        ("metadata", "postgres"),
        ("db-connect", "postgres"),
    ],
)
def test_inspection_selects_exact_environment(
    monkeypatch, environment, action, service
):
    calls = []

    def run(args, **kwargs):
        calls.append(args)
        return SimpleNamespace(stdout="selected-container\n", returncode=0)

    monkeypatch.setattr(runtime.subprocess, "run", run)
    runtime.run(action, environment, "unused-service")
    assert f"label=com.docker.compose.project=airflow-{environment}" in calls[0]
    assert f"label=com.docker.compose.service={service}" in calls[0]
    assert "label=com.docker.compose.oneoff=False" in calls[0]
    assert calls[1][:2] == ["docker", "exec"]
    assert "selected-container" in calls[1]
    if action == "sales":
        assert calls[1][-1] == "/opt/airflow/scripts/inspect_sales.py"
    else:
        assert "PGOPTIONS=-c default_transaction_read_only=on" in calls[1]
        assert "-X" in calls[1]
        assert f"PROMPT1=[{environment}] %/> " in calls[1]
        assert f"PROMPT2=[{environment}] ...> " in calls[1]


@pytest.mark.parametrize("output", ["", "one\ntwo\n"])
def test_missing_or_ambiguous_container_never_executes(monkeypatch, output):
    calls = []

    def run(args, **kwargs):
        calls.append(args)
        return SimpleNamespace(stdout=output)

    monkeypatch.setattr(runtime.subprocess, "run", run)
    with pytest.raises(RuntimeError, match="Expected one"):
        runtime.run("sales", "prod", "unused")
    assert len(calls) == 1


def test_invalid_environment_fails_before_docker():
    result = subprocess.run(
        ["python3", str(SPEC.origin), "sales", "--env", "production"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "invalid choice" in result.stderr


def test_docker_error_is_not_swallowed(monkeypatch):
    def fail(*args, **kwargs):
        raise subprocess.CalledProcessError(7, ["docker"])

    monkeypatch.setattr(runtime.subprocess, "run", fail)
    with pytest.raises(subprocess.CalledProcessError):
        runtime.run("sales", "prod", "unused")


@pytest.mark.parametrize("environment", ["dev", "test", "prod"])
def test_password_command_uses_selected_api_container(monkeypatch, environment):
    calls = []

    def run(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(stdout="api-container\n", returncode=0)

    monkeypatch.setattr(runtime.subprocess, "run", run)
    runtime.run("airflow-password", environment, "unused")
    lookup = calls[0][0]
    assert f"label=com.docker.compose.project=airflow-{environment}" in lookup
    assert "label=com.docker.compose.service=airflow-api-server" in lookup
    command, options = calls[1]
    assert command[:3] == ["docker", "exec", "api-container"]
    assert not options.get("capture_output")
    assert "simple_auth_manager_passwords_file" in command[-1]
    compile(command[-1], "<password-reader>", "exec")


@pytest.mark.parametrize("mixed", [False, True])
def test_image_selection_requires_consistent_services(monkeypatch, mixed):
    images = iter(
        [
            "sha256:" + "a" * 64,
            "sha256:" + "b" * 64 if mixed else "sha256:" + "a" * 64,
            "sha256:" + "a" * 64,
        ]
    )
    monkeypatch.setattr(runtime, "container_id", lambda env, service: service)
    monkeypatch.setattr(
        runtime.subprocess, "run", lambda *a, **k: SimpleNamespace(stdout=next(images))
    )
    if mixed:
        with pytest.raises(RuntimeError, match="different images"):
            runtime.deployed_image("test")
    else:
        assert runtime.deployed_image("test") == "sha256:" + "a" * 64


def test_ui_apply_reuses_image_and_only_recreates_api(monkeypatch):
    calls = []
    image = "sha256:" + "a" * 64
    monkeypatch.setattr(runtime, "deployed_image", lambda env: image)
    monkeypatch.setattr(
        runtime.subprocess, "run", lambda args, **kwargs: calls.append((args, kwargs))
    )
    runtime.run("ui-apply", "test", "unused")
    args, kwargs = calls[0]
    assert kwargs["env"]["AIRFLOW_IMAGE"] == image
    assert "--no-deps" in args
    assert args[-1] == "airflow-api-server"
    assert "never" in args
    assert any(arg.endswith("secrets/test.env") for arg in args)
