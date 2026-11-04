"""Intration teests for persisted sales verification."""

import sqlite3
import unittest
from dataclasses import replace
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from sales_lab.checks import check_loaded_sales
from sales_lab.load import load_sales
from sales_lab.transform import Sale


class CheckLoadedSalesTEst(unittest.TestCase):
    def setUp(self) -> None:
        temporary_directory = TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        self.db_path = Path(temporary_directory.name) / "sales.sqlite"

        self.sales = [
            Sale(1, date(2026, 10, 1), "C001", 1995),
            Sale(2, date(2026, 10, 2), "C002", 0),
        ]

    def test_matching_batch_passes(self) -> None:
        load_sales(self.db_path, self.sales)
        check_loaded_sales(self.db_path, self.sales)

    def test_existing_sales_outside_batch_are_allowed(self) -> None:
        load_sales(self.db_path, self.sales)
        check_loaded_sales(self.db_path, self.sales[:1])

    def test_missing_sale_is_rejected(self) -> None:
        load_sales(self.db_path, self.sales[:1])
        with self.assertRaisesRegex(ValueError, "missing"):
            check_loaded_sales(self.db_path, self.sales)

    def test_each_mismatched_field_is_rejected(self) -> None:
        load_sales(self.db_path, self.sales)

        changed_sales = {
            "sale_date": replace(self.sales[0], sale_date=date(2026, 10, 3)),
            "customer_id": replace(self.sales[0], customer_id="C009"),
            "amount_cents": replace(self.sales[0], amount_cents=2500),
        }
        for field, changed_sale in changed_sales.items():
            with self.subTest(field=field):
                with self.assertRaisesRegex(
                    ValueError, "Stored sale does not match the expected values"
                ):
                    check_loaded_sales(self.db_path, [changed_sale])

    def test_missing_database_is_not_created(self) -> None:
        with self.assertRaises(sqlite3.OperationalError):
            check_loaded_sales(self.db_path, self.sales)

        self.assertFalse(self.db_path.exists())

    def test_empty_expected_batch_is_allowed(self) -> None:
        load_sales(self.db_path, self.sales)
        check_loaded_sales(self.db_path, [])
