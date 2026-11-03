"""Load validated sales batch onto SQLite."""

import sqlite3
from collections.abc import Sequence
from pathlib import Path

from sales_lab.transform import Sale


def load_sales(
        db_path: Path,
        sales: Sequence[Sale],
        sql_dir: Path,
) -> None:
    """Load an already validated batch in one transaction..

    Create the sales table if necessary.
    Update existing sale IDs and insert new ones.
    Own and close the database connection.
    """


    schema_sql = (sql_dir / "schema.sql").read_text(encoding="utf-8")
    upsert_sql = (sql_dir / "upsert_sales.sql").read_text(encoding="utf-8")

    parameters = [
        {
            "sale_id": sale.sale_id,
            "sale_date": sale.sale_date.isoformat(),
            "customer_id": sale.customer_id,
            "amount_cents": sale.amount_cents
        }
        for sale in sales
    ]
    connection = sqlite3.connect(db_path, isolation_level=None)

    try:
        connection.execute("BEGIN")
        connection.execute(schema_sql)
        connection.executemany(upsert_sql, parameters)
        connection.execute("COMMIT")
    finally:
        try:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
        finally:
            connection.close()
