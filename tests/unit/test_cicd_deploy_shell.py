"""Run the real deployment shell script against a fake Docker CLI."""

import os
import subprocess
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).resolve().parents[2] / "infra/gitea/deply-repo/scripts/deploy.sh"
)


@pytest.mark.parametrize(
    "mode,target,expected",
    [
        ("success", "dev", 0),
        ("success", "test", 0),
        ("success", "prod", 0),
        ("active", "dev", 1),
        ("wrong-image", "test", 1),
        ("failed", "test", 1),
        ("missing-input", "dev", 1),
        ("success", "invalid", 2),
    ],
)
def test_deployment_guards_and_result(tmp_path, mode, target, expected):
    docker = tmp_path / "docker"
    docker.write_text("""#!/bin/sh
printf '%s\\n' "$*" >> "$MOCK_TRACE"
case "$*" in
  "run --rm --mount "*) test "$MOCK_MODE" != missing-input ;;
  *"to_regclass"*) echo t ;;
  *"SELECT count(*)"*)
    if test "$MOCK_MODE" = active; then echo 1; else echo 0; fi ;;
  *"SELECT state"*)
    if test "$MOCK_MODE" = failed; then echo failed; else echo success; fi ;;
  "inspect "*)
    if test "$MOCK_MODE" = wrong-image; then echo sha256:wrong; else echo "$AIRFLOW_IMAGE"; fi ;;
  *"ps -q"*) echo example-container ;;
esac
""")
    docker.chmod(0o755)
    result_file = tmp_path / "smoke-result"
    trace = tmp_path / "trace"
    env = dict(
        os.environ,
        PATH=f"{tmp_path}:{os.environ['PATH']}",
        MOCK_MODE=mode,
        MOCK_TRACE=str(trace),
        LAB_HOST_ROOT="/example/project with spaces",
        AIRFLOW_IMAGE="sha256:" + "b" * 64,
        DEPLOY_RESULT_FILE=str(result_file),
    )
    result = subprocess.run(
        ["sh", str(SCRIPT), target], env=env, capture_output=True, text=True
    )
    assert result.returncode == expected, result.stdout + result.stderr
    assert result_file.exists() == (expected == 0)
    if expected == 0:
        assert result_file.read_text().startswith("deploy-")
        assert f"--project-name airflow-{target}" in trace.read_text()
    if mode in {"active", "missing-input"}:
        assert "stop --timeout" not in trace.read_text()
