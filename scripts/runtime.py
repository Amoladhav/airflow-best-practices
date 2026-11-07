"""Inspect existing Airflow environments without selecting or changing a release."""

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path


def container_id(environment: str, service: str) -> str:
    result = subprocess.run(
        [
            "docker",
            "ps",
            "--all",
            "--quiet",
            "--filter",
            f"label=com.docker.compose.project=airflow-{environment}",
            "--filter",
            f"label=com.docker.compose.service={service}",
            "--filter",
            "label=com.docker.compose.oneoff=False",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    containers = result.stdout.split()
    if len(containers) != 1:
        raise RuntimeError(
            f"Expected one {service} container in airflow-{environment}; "
            f"found {len(containers)}. Check 'make status ENV={environment}'."
        )
    return containers[0]


def deployed_image(environment: str) -> str:
    images = set()
    for service in ("airflow-api-server", "airflow-scheduler", "airflow-dag-processor"):
        container = container_id(environment, service)
        result = subprocess.run(
            ["docker", "inspect", "--format", "{{.Image}}", container],
            check=True,
            capture_output=True,
            text=True,
        )
        image = result.stdout.strip()
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", image):
            raise RuntimeError("Docker returned an invalid image ID")
        images.add(image)
    if len(images) != 1:
        raise RuntimeError(
            "Airflow services use different images; resolve the incomplete deployment first."
        )
    return images.pop()


def compose(environment: str, arguments: list[str]) -> None:
    root = Path(__file__).resolve().parents[1]
    image = deployed_image(environment)
    subprocess.run(
        [
            "docker",
            "compose",
            "--project-directory",
            str(root),
            "--project-name",
            f"airflow-{environment}",
            "--env-file",
            str(root / f"environments/{environment}.env"),
            "--env-file",
            str(root / f"secrets/{environment}.env"),
            "-f",
            str(root / "infra/docker/compose.runtime.yaml"),
            *arguments,
        ],
        env=dict(os.environ, AIRFLOW_IMAGE=image),
        check=True,
    )


def run(action: str, environment: str, service: str) -> None:
    if action == "image":
        print(deployed_image(environment))
        return
    if action == "ui-apply":
        compose(
            environment,
            [
                "up",
                "-d",
                "--no-deps",
                "--no-build",
                "--pull",
                "never",
                "--force-recreate",
                "--wait",
                "airflow-api-server",
            ],
        )
        return
    if action == "status":
        args = [
            "docker",
            "ps",
            "--all",
            "--filter",
            f"label=com.docker.compose.project=airflow-{environment}",
            "--format",
            "table {{.Names}}\t{{.Status}}\t{{.Ports}}",
        ]
    elif action == "logs":
        args = [
            "docker",
            "logs",
            "--follow",
            "--tail",
            "100",
            container_id(environment, service),
        ]
    elif action == "sales":
        args = [
            "docker",
            "exec",
            container_id(environment, "airflow-scheduler"),
            "python",
            "/opt/airflow/scripts/inspect_sales.py",
        ]
    elif action == "airflow-password":
        args = [
            "docker",
            "exec",
            container_id(environment, "airflow-api-server"),
            "python",
            "-c",
            "import json, os; from pathlib import Path; "
            "from airflow.configuration import conf; "
            "configured = conf.get('core', 'simple_auth_manager_passwords_file', fallback=''); "
            "path = Path(configured) if configured else "
            "Path(os.environ.get('AIRFLOW_HOME', '/opt/airflow')) / "
            "'simple_auth_manager_passwords.json.generated'; "
            "print(json.loads(path.read_text())['admin'])",
        ]
    elif action in {"db-connect", "metadata"}:
        args = ["docker", "exec", "-i"]
        if sys.stdin.isatty() and sys.stdout.isatty():
            args.append("-t")
        args += [
            "-e",
            "PGOPTIONS=-c default_transaction_read_only=on",
            container_id(environment, "postgres"),
            "psql",
            "-X",
            "-v",
            "ON_ERROR_STOP=1",
            "-v",
            f"PROMPT1=[{environment}] %/> ",
            "-v",
            f"PROMPT2=[{environment}] ...> ",
            "-U",
            "airflow",
            "-d",
            "airflow",
        ]
    else:
        raise ValueError(f"Unknown action: {action}")
    subprocess.run(args, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action",
        choices=[
            "image",
            "ui-apply",
            "compose",
            "status",
            "logs",
            "sales",
            "db-connect",
            "metadata",
            "airflow-password",
        ],
    )
    parser.add_argument("--env", choices=["dev", "test", "prod"], default="dev")
    parser.add_argument("--service", default="airflow-scheduler")
    args, remaining = parser.parse_known_args()
    if remaining and args.action != "compose":
        parser.error("Unexpected arguments")
    try:
        if args.action == "compose":
            if remaining[:1] == ["--"]:
                remaining = remaining[1:]
            if not remaining:
                parser.error("Compose command required")
            compose(args.env, remaining)
        else:
            run(args.action, args.env, args.service)
    except (RuntimeError, OSError) as exc:
        raise SystemExit(str(exc)) from None
    except subprocess.CalledProcessError as exc:
        raise SystemExit(exc.returncode) from None
    except KeyboardInterrupt:
        raise SystemExit(130) from None


if __name__ == "__main__":
    main()
