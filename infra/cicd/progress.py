"""Plain-terminal setup progress, with private local logs and optional colors."""

import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


def duration(seconds: float) -> str:
    minutes, seconds = divmod(int(seconds), 60)
    return f"{minutes:02d}:{seconds:02d}"


class Progress:
    def __init__(self, root: Path):
        self.started = time.monotonic()
        self.stage_started = self.started
        self.current = None
        self.color = sys.stdout.isatty() and "NO_COLOR" not in os.environ
        directory = root / "logs" / "setup"
        directory.mkdir(parents=True, exist_ok=True)
        self.path = directory / (
            datetime.now().strftime("%Y%m%d-%H%M%S") + f"-{os.getpid()}.log"
        )
        fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        self.log = os.fdopen(fd, "w", buffering=1)

    def emit(self, status: str, message: str):
        colors = {"RUN": "36", "WAIT": "36", "OK": "32", "FAIL": "31"}
        elapsed = duration(time.monotonic() - self.started)
        self.log.write(f"[{elapsed}] {status:<4} {message}\n")
        label = f"{status:<4}"
        if self.color:
            label = f"\033[{colors.get(status, '0')}m{label}\033[0m"
        print(
            f"[{elapsed}] {label} {message}",
            flush=True,
        )

    def stage(self, message: str):
        if self.current:
            self.emit(
                "OK",
                f"{self.current} ({duration(time.monotonic() - self.stage_started)})",
            )
        self.current = message
        self.stage_started = time.monotonic()
        self.emit("RUN", message)

    def finish(self):
        if self.current:
            self.emit(
                "OK",
                f"{self.current} ({duration(time.monotonic() - self.stage_started)})",
            )
        self.current = None
        self.emit("OK", "Setup complete — all three environments verified")
        print(f"Setup log: {self.path}", flush=True)

    def fail(self, message: str):
        self.emit("FAIL", f"{self.current or 'Preflight'}: {message}")
        print(
            f"Setup log: {self.path}\nCorrect the error and rerun the same setup command to resume.",
            flush=True,
        )

    def run(self, args, **kwargs):
        # Only non-sensitive command output is logged. Credential-generating commands
        # use provision.command(capture=True) and never pass through this method.
        with subprocess.Popen(
            args, text=True, stdout=self.log, stderr=subprocess.STDOUT, **kwargs
        ) as process:
            while True:
                try:
                    result = process.wait(timeout=15)
                    break
                except subprocess.TimeoutExpired:
                    self.emit(
                        "WAIT",
                        "Docker/Git operation still running — detailed output is in the setup log",
                    )
        if result:
            raise subprocess.CalledProcessError(result, args)
        return ""

    def close(self):
        self.log.close()
