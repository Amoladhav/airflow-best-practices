"""Integration tests for SQLite sales loading."""

import sqlite3
import unittest
from contextlib import closing
from dataclasses import replace
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from sales_lab.load import load_sales
from sales_lab.transform import Sale

SQL_DIR = Path(__file__).resolve().parents[2] / "sql"


class LoadSalesTest(unittest.TestCase):
    def setUp(self) -> None:
        temporary_directory = TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        self.db_path = Path(temporary_directory.name) / "sales.sqlite"

        self.sales = [
            Sale(1, date(2026, 10, 1), "C001", 1995),
            Sale(2, date(2026, 10, 2), "C002", 0)
        ]


    def stored_rows(self) -> list[tuple[int,str,str,int]]:
        with closing(sqlite3.connect(self.db_path)) as connection:
            return connection.execute(
                """
                SELECT sale_id, sale_date, customer_id, amount_cents
                FROM sales
                ORDER BY sale_id
                """
            ).fetchall()

    def test_initial_load_stored_expected_rows(self) -> None:
        load_sales(self.db_path, self.sales, SQL_DIR)

        self.assertEqual(
            self.stored_rows(),
            [
                (1, "2026-10-01", "C001", 1995),
                (2, "2026-10-02", "C002", 0)
                ],

        )

    def test_identical_replay_leaves_contents_unchanged(self) -> None:
        load_sales(self.db_path, self.sales, SQL_DIR)
        before = self.stored_rows()

        load_sales(self.db_path, self.sales, SQL_DIR)
        self.assertEqual(self.stored_rows(), before)
        self.assertEqual(len(self.stored_rows()), len(before))


    def test_failed_batch_rolls_back_and_allows_recovery(self) -> None:
        load_sales(self.db_path, self.sales, SQL_DIR)
        before = self.stored_rows()

        with closing(
            sqlite3.connect(self.db_path, isolation_level=None)
        ) as connection:
            connection.execute(
                """
                CREATE TRIGGER reject_sales_three
                BEFORE INSERT ON sales
                WHEN NEW.sale_id = 3
                BEGIN
                    SELECT RAISE(ABORT, 'simulated write failure');
                END;
                """
            )
            updated_sales = replace(self.sales[0], amount_cents=2500)
            new_sale = Sale(4, date(2026, 10, 3), "C004", 500)
            rejected_sale = Sale(3, date(2026, 10, 3), "C003", 100)

            with self.assertRaisesRegex(
                sqlite3.IntegrityError, "simulated write failure"
            ):
                load_sales(
                    self.db_path,
                    [updated_sales, new_sale, rejected_sale],
                    SQL_DIR,
                )

            self.assertEqual(self.stored_rows(), before)

            #A subsequent valid batch must still succeed.
            load_sales(
                self.db_path,
                [updated_sales, new_sale],
                SQL_DIR,
            )

            self.assertEqual(
                self.stored_rows(),
                [
                    (1, "2026-10-01", "C001", 2500),
                    (2, "2026-10-02", "C002", 0),
                    (4, "2026-10-03", "C004", 500)
                ],
            )

    def test_existing_id_updates_without_duplicating(self) -> None:
        load_sales(self.db_path, self.sales, SQL_DIR)

        updated_sale = replace(
            self.sales[0],
            sale_date=date(2026, 10, 3),
            customer_id="C009",
            amount_cents=2500,
            )

        load_sales(self.db_path, [updated_sale], SQL_DIR)

        self.assertEqual(
            self.stored_rows(),
            [
                (1, "2026-10-03", "C009", 2500),
                (2, "2026-10-02", "C002", 0)
            ]
        )
