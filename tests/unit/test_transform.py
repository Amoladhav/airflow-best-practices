"""Behavioral tests for source-record validation."""

import unittest
from datetime import date

from sales_lab.transform import Sale, transform_batch, transform_row


def source_row(**changes: str) -> dict[str, str]:
    row = {
        "sale_id": "1",
        "sale_date": "2026-10-01",
        "customer_id": "C001",
        "amount": "19.95",
    }
    return row | changes


class TransformRowTests(unittest.TestCase):
    def test_valid_row_becomes_typed_sale(self):
        self.assertEqual(
            transform_row(source_row()),
            Sale(1, date(2026, 10, 1), "C001", 1995),
        )

    def test_money_boundaries(self):
        for amount, expected in [
            ("0.00", 0),
            ("0.01", 1),
            ("0.29", 29),
            ("10", 1000),
            ("10.5", 1050),
        ]:
            with self.subTest(amount=amount):
                self.assertEqual(
                    transform_row(source_row(amount=amount)).amount_cents,
                    expected,
                )

    def test_surrounding_whitespace_is_removed(self):
        actual = transform_row(source_row(customer_id=" C001 ", amount=" 19.95 "))
        self.assertEqual(actual.customer_id, "C001")
        self.assertEqual(actual.amount_cents, 1995)

    def test_invalid_fields_are_rejected(self):
        cases = [
            ("sale_id", "0"),
            ("sale_id", "-1"),
            ("sale_id", "1.5"),
            ("sale_id", "9223372036854775808"),
            ("sale_date", "2026-02-30"),
            ("sale_date", "20261001"),
            ("customer_id", "   "),
            ("amount", "-0.01"),
            ("amount", "1.001"),
            ("amount", "NaN"),
            ("amount", "Infinity"),
            ("amount", "1e2"),
            ("amount", "92233720368547758.08"),
        ]
        for field, value in cases:
            with self.subTest(field=field, value=value):
                with self.assertRaisesRegex(ValueError, field):
                    transform_row(source_row(**{field: value}))

    def test_missing_field_is_rejected(self):
        row = source_row()
        del row["amount"]
        with self.assertRaisesRegex(ValueError, "amount"):
            transform_row(row)


class TransformBatchTests(unittest.TestCase):
    def test_distinct_ids_produce_distinct_sales(self):
        rows = [
            source_row(sale_id="1"),
            source_row(sale_id="2"),
        ]
        sales = transform_batch(rows)
        self.assertEqual(len(sales), 2)
        self.assertEqual(sales[0].sale_id, 1)
        self.assertEqual(sales[1].sale_id, 2)

    def test_two_rows_with_same_id_are_rejected(self):
        rows = [
            source_row(sale_id="1", amount="19.95"),
            source_row(sale_id="1", amount="20.00"),
        ]
        with self.assertRaisesRegex(ValueError, "duplicate sale_id"):
            transform_batch(rows)

    def test_invalid_second_row_is_rejected(self):
        rows = [
            source_row(sale_id="1"),
            source_row(sale_id="2", amount="invalid"),
        ]
        with self.assertRaisesRegex(ValueError, "amount"):
            transform_batch(rows)

    def test_empty_input_returns_empty_list(self):
        self.assertEqual(transform_batch([]), [])
