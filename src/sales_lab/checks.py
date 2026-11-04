"""Verify that a validated sales batch exists in SQLite."""

import sqlite3
from collections.abc import Sequence
from contextlib import closing
from importlib.resources import files
from pathlib import Path

from sales_lab.transform import Sale


def check_loaded_sales(db_path: Path, expected_sales: Sequence[Sale]) -> None:
    database_uri = db_path.resolve().as_uri() + "?mode=ro"
    query = (
        files("sales_lab")
        .joinpath("sql", "select_sales.sql")
        .read_text(encoding="utf-8")
    )

    with closing(sqlite3.connect(database_uri, uri=True)) as connection:
        rows = connection.execute(query).fetchall()

        stored_sales = {
            sale_id: (sale_date, customer_id, amount_cents)
            for sale_id, sale_date, customer_id, amount_cents in rows
        }

        for sale in expected_sales:
            expected_values = (
                sale.sale_date.isoformat(),
                sale.customer_id,
                sale.amount_cents,
            )

            if sale.sale_id not in stored_sales:
                raise ValueError("expected sale is missing from the database")

            if stored_sales[sale.sale_id] != expected_values:
                raise ValueError("Stored sale does not match the expected values")
