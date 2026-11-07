"""Build once, verify dev/test, and promote the recorded artifact to production."""

import argparse
import fcntl
import json
import os
import re
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from gitea_api import GateError, from_environment

SCRIPTS = Path(__file__).resolve().parent


def command(args: list[str], cwd: Path, capture: bool = False, env=None) -> str:
    result = subprocess.run(
        args,
        cwd=cwd,
        env=env,
        check=True,
        text=True,
        stdout=subprocess.PIPE if capture else None,
    )
    return (result.stdout or "").strip()


def save(path: Path, data: dict) -> None:
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(data, indent=2) + "\n")
    temp.replace(path)


def image_source(image: str, checkout: Path, revision: str) -> None:
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", image):
        raise GateError("Release must use a full immutable image ID")
    label = command(
        [
            "docker",
            "image",
            "inspect",
            image,
            "--format",
            '{{index .Config.Labels "org.opencontainers.image.revision"}}',
        ],
        checkout,
        capture=True,
    )
    if label != revision:
        raise GateError("Image source label does not match release")


def deploy(target: str, image: str, checkout: Path, record: dict, directory: Path):
    """Record success only after container identity and scheduler checks pass."""
    attempt = {
        "revision": record["revision"],
        "image": image,
        "environment": target,
        "status": "deploying",
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    save(directory / f"{target}-attempt.json", attempt)
    result_file = checkout / f".smoke-{target}"
    env = dict(os.environ, AIRFLOW_IMAGE=image, DEPLOY_RESULT_FILE=str(result_file))
    try:
        command(["sh", str(SCRIPTS / "deploy.sh"), target], checkout, env=env)
    except (subprocess.CalledProcessError, OSError):
        save(directory / f"{target}-attempt.json", attempt | {"status": "failed"})
        raise
    success = attempt | {
        "status": "verified",
        "dag_run_id": result_file.read_text().strip(),
        "verified_at": datetime.now(timezone.utc).isoformat(),
    }
    record[target] = success
    save(directory / f"{record['revision']}.json", record)
    save(directory / f"{target}.json", success)
    save(directory / f"{target}-attempt.json", success)


def release(branch: str, revision: str, run_id: str, operation: str) -> None:
    if operation not in {"release", "rollback"}:
        raise GateError("Unsupported release operation")
    if branch not in {"dev", "main"} or not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise GateError("Expected dev/main and a full lowercase commit SHA")
    api = from_environment()
    directory = Path(os.environ.get("RELEASE_DIR", "/releases"))
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / "release.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        manifest = directory / f"{revision}.json"
        record = (
            json.loads(manifest.read_text())
            if manifest.exists()
            else {
                "revision": revision,
            }
        )
        if operation == "rollback":
            if branch != "main" or record.get("prod", {}).get("status") != "verified":
                raise GateError(
                    "Rollback requires a previously verified production release"
                )
        else:
            api.verify_ci(run_id, branch, revision)
        if branch == "main" and record.get("test", {}).get("status") != "verified":
            raise GateError("Production requires a recorded successful test deployment")

        with tempfile.TemporaryDirectory(prefix="airflow-release-") as temp:
            checkout = Path(temp)
            api.git(["init", "--quiet"], checkout)
            api.git(
                ["remote", "add", "origin", f"{api.url}/{api.repository}.git"], checkout
            )
            api.git(["fetch", "--no-tags", "origin", revision], checkout)
            api.git(["checkout", "--detach", revision], checkout)

            if branch == "dev":
                if "image" not in record:
                    tag = f"airflow-sales-lab:{revision}"
                    exists = (
                        subprocess.run(
                            ["docker", "image", "inspect", tag],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                        ).returncode
                        == 0
                    )
                    if not exists:
                        command(
                            [
                                "docker",
                                "build",
                                "--file",
                                str(
                                    Path("infra/docker/Dockerfile")
                                    if (checkout / "infra/docker/Dockerfile").is_file()
                                    else Path("Dockerfile")
                                ),
                                "--build-arg",
                                f"SOURCE_REVISION={revision}",
                                "--tag",
                                tag,
                                ".",
                            ],
                            checkout,
                        )
                    record["image"] = command(
                        [
                            "docker",
                            "image",
                            "inspect",
                            tag,
                            "--format",
                            "{{.Id}}",
                        ],
                        checkout,
                        capture=True,
                    )
                    image_source(record["image"], checkout, revision)
                    save(manifest, record)
                image = record["image"]
                image_source(image, checkout, revision)
                command(
                    [
                        "docker",
                        "run",
                        "--rm",
                        "-e",
                        "AIRFLOW__CORE__LOAD_EXAMPLES=False",
                        "--entrypoint",
                        "python",
                        image,
                        "-c",
                        "from airflow.models import DagBag; "
                        'bag = DagBag(dag_folder="/opt/airflow/dags"); '
                        "assert not bag.import_errors, bag.import_errors; "
                        'assert "sales_etl" in bag.dags; print("Packaged DAG passed")',
                    ],
                    checkout,
                )
                api.verify_ci(run_id, branch, revision)
                deploy("dev", image, checkout, record, directory)
                api.verify_ci(run_id, branch, revision)
                api.git(["fetch", "origin", "test"], checkout)
                api.git(
                    ["merge-base", "--is-ancestor", "FETCH_HEAD", revision], checkout
                )
                api.git(["push", "origin", f"{revision}:refs/heads/test"], checkout)
                deploy("test", image, checkout, record, directory)
            else:
                image = record["image"]
                image_source(image, checkout, revision)
                if operation != "rollback":
                    api.verify_ci(run_id, branch, revision)
                deploy("prod", image, checkout, record, directory)
            print(f"Verified {branch} release {revision} using {image}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--branch", choices=["dev", "main"], required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--ci-run-id", default="")
    parser.add_argument(
        "--operation", choices=["release", "rollback"], default="release"
    )
    args = parser.parse_args()
    try:
        release(args.branch, args.revision, args.ci_run_id, args.operation)
    except (GateError, subprocess.CalledProcessError, OSError) as exc:
        raise SystemExit(f"Release stopped: {exc}") from None


if __name__ == "__main__":
    main()
