"""Owner-run Gitea startup and first administrator creation."""

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COMPOSE = [
    "docker",
    "compose",
    "--project-directory",
    str(ROOT),
    "-f",
    str(ROOT / "infra/docker/compose.cicd.yaml"),
]
ADMIN = [
    *COMPOSE,
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
]


def has_admin(output: str) -> bool:
    lines = [line.strip() for line in output.splitlines()]
    headers = [i for i, line in enumerate(lines) if re.match(r"ID\s+Username\s+", line)]
    if len(headers) != 1:
        raise RuntimeError("Unrecognized Gitea user-list output; no account created.")
    return any(re.match(r"\d+\s+", line) for line in lines[headers[0] + 1 :])


def bootstrap() -> None:
    subprocess.run(
        [*COMPOSE, "up", "-d", "--wait", "--wait-timeout", "180", "gitea"], check=True
    )
    result = subprocess.run(
        [*ADMIN, "list", "--admin"], check=True, capture_output=True, text=True
    )
    if has_admin(result.stdout):
        print("Gitea is ready; an administrator already exists. No account changed.")
        return
    username = input("First administrator username [cicd]: ").strip() or "cicd"
    email = input("Administrator email: ").strip()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", username) or "@" not in email:
        raise RuntimeError("Provide a valid username and email; no account created.")
    print(
        "Gitea will display a generated password locally. Save it before closing this terminal."
    )
    subprocess.run(
        [
            *ADMIN,
            "create",
            "--username",
            username,
            "--email",
            email,
            "--admin",
            "--random-password",
            "--random-password-length",
            "32",
            "--must-change-password",
        ],
        check=True,
    )
    print("Sign in at http://localhost:3000 and change the generated password.")


if __name__ == "__main__":
    try:
        bootstrap()
    except (OSError, RuntimeError) as exc:
        raise SystemExit(str(exc)) from None
    except subprocess.CalledProcessError as exc:
        raise SystemExit(exc.returncode) from None
