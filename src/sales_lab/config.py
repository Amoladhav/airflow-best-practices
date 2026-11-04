"""Read Sales pipeline configuration at execution time."""

import os
from pathlib import Path


def get_sales_paths() -> tuple[Path, Path]:
    """Return the configured input CSV and output database paths."""

    paths = []

    for name in ("SALES_CSV_PATH", "SALES_DB_PATH"):
        value = os.environ.get(name)
        if value is None or not value.strip():
            raise ValueError(f"Required environment variable {name} is missing")

        paths.append(Path(value))

    return paths[0], paths[1]
