"""Safety contracts for the fresh-install orchestrator."""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def provision(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "infra/cicd"))
    # setup.py imports the controller library using its canonical path.
    spec = importlib.util.spec_from_file_location(
        "provision", ROOT / "infra/cicd/provision.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_secrets_are_private_and_never_overwritten(provision, tmp_path):
    target = tmp_path / "secrets" / "token"
    provision.write_secret(target, "synthetic")
    assert target.stat().st_mode & 0o777 == 0o600
    with pytest.raises(FileExistsError):
        provision.write_secret(target, "replacement")
    assert target.read_text() == "synthetic\n"


def test_token_parser_ignores_logs_and_rejects_ambiguity(provision):
    token = "a" * 40
    assert provision.parse_token("warning\n" + token) == token
    for response in ("", "error", token + "\n" + token):
        with pytest.raises(provision.GateError):
            provision.parse_token(response)


def test_wait_timeout_is_bounded(provision, monkeypatch):
    clock = [0]
    monkeypatch.setattr(provision.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(
        provision.time,
        "sleep",
        lambda seconds: clock.__setitem__(0, clock[0] + seconds),
    )
    with pytest.raises(provision.GateError, match="Timed out"):
        provision.wait_for("example", lambda: None, timeout=5)


def test_wait_reports_status_and_returns_result(provision, monkeypatch, capsys):
    clock = [0]
    monkeypatch.setattr(provision.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(
        provision.time,
        "sleep",
        lambda seconds: clock.__setitem__(0, clock[0] + seconds),
    )
    result = provision.wait_for(
        "deployment",
        lambda: {"verified": True} if clock[0] >= 20 else None,
        progress=lambda: "dev CI: success | deployment: in_progress",
    )
    output = capsys.readouterr().out
    assert result == {"verified": True}
    assert output.count("dev CI: success") == 2
    assert "00:15" in output


def test_sensitive_capture_never_enters_progress_log(provision, tmp_path):
    import sys

    progress = provision.Progress(tmp_path)
    provision.REPORTER = progress
    try:
        value = provision.command(
            [sys.executable, "-c", "print('synthetic-credential')"], capture=True
        )
        assert value == "synthetic-credential"
        assert "synthetic-credential" not in progress.path.read_text()
    finally:
        progress.close()


def test_command_failure_identifies_log_without_ansi(
    provision, tmp_path, capsys, monkeypatch
):
    import subprocess
    import sys

    monkeypatch.setenv("NO_COLOR", "1")
    progress = provision.Progress(tmp_path)
    try:
        progress.stage("Starting services")
        with pytest.raises(subprocess.CalledProcessError):
            progress.run([sys.executable, "-c", "print('diagnostic detail'); exit(7)"])
        progress.fail("Docker command failed")
        output = capsys.readouterr().out
        assert "FAIL" in output and str(progress.path) in output
        assert "\033[" not in output
        assert "diagnostic detail" in progress.path.read_text()
        assert progress.path.stat().st_mode & 0o777 == 0o600
    finally:
        progress.close()
