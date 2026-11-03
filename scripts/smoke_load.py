"""Demonstrates CSV ingestion and SQLite loading in temporary storage."""

import sqlite3
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory

from sales_lab.ingest import read_sales_csv
from sales_lab.load import load_sales

def main() -> None:
    project_root = Path(__file__).resolve().parents[1]

    with (project_root / "sample_data" / "sales.csv").open(
        encoding="utf-8",
        newline=""
    ) as stream:
        sales = read_sales_csv(stream)

    with TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "sales.sqlite"

        load_sales(
            db_path=db_path,
            sales=sales,
        )

        with closing(sqlite3.connect(db_path)) as connection:
            rows = connection.execute(
                """
                SELECT sale_id, sale_date, customer_id, amount_cents
                FROM sales
                ORDER BY sale_id
                """
            ).fetchall()
        print(f"Stored {len(rows)} sales:")

        for row in rows:
            print(row)

if __name__ == "__main__":
    main()
