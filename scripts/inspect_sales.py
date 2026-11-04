"""Inspect persisted sales without modifying the database."""

import sqlite3
from contextlib import closing
from importlib.resources import files

from sales_lab.config import get_sales_paths


def main() -> None:
    _, db_path = get_sales_paths()
    database_uri = db_path.resolve().as_uri() + "?mode=ro"

    query = (
        files("sales_lab")
        .joinpath("sql", "select_sales.sql")
        .read_text(encoding="utf-8")
    )

    with closing(sqlite3.connect(database_uri, uri=True)) as connection:
        rows = connection.execute(query).fetchall()

    print(f"Row count: {len(rows)}")
    for row in rows:
        print(row)


if __name__ == "__main__":
    main()
