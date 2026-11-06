"""Behavior tests for daily sales reporting."""

import unittest
from datetime import date

from sales_lab.reporting import DailySalesTotal, summarize_daily_sales
from sales_lab.transform import Sale


class DailySalesTests(unittest.TestCase):
    def test_exact_total_sorted_by_date(self):
        sales = [
            Sale(
                sale_id=1,
                sale_date=date(2024, 10, 2),
                customer_id="C001",
                amount_cents=100,
            ),
            Sale(
                sale_id=2,
                sale_date=date(2024, 10, 1),
                customer_id="C002",
                amount_cents=200,
            ),
            Sale(
                sale_id=3,
                sale_date=date(2024, 10, 2),
                customer_id="C003",
                amount_cents=0,
            ),
            Sale(
                sale_id=4,
                sale_date=date(2024, 10, 3),
                customer_id="C004",
                amount_cents=100,
            ),
        ]
        expected = [
            DailySalesTotal(
                sale_date=date(2024, 10, 1), sale_count=1, total_amount_cents=200
            ),
            DailySalesTotal(
                sale_date=date(2024, 10, 2), sale_count=2, total_amount_cents=100
            ),
            DailySalesTotal(
                sale_date=date(2024, 10, 3), sale_count=1, total_amount_cents=100
            ),
        ]
        result = summarize_daily_sales(sales)
        self.assertEqual(result, expected)

    def test_empty_input_returns_empty_list(self):
        sales = []
        expected = []
        result = summarize_daily_sales(sales)
        self.assertEqual(result, expected)

    def test_repeated_reporting_preserves_input(self):
        sales = [
            Sale(
                sale_id=1,
                sale_date=date(2024, 10, 2),
                customer_id="C001",
                amount_cents=100,
            ),
            Sale(
                sale_id=2,
                sale_date=date(2024, 10, 1),
                customer_id="C002",
                amount_cents=200,
            ),
            Sale(
                sale_id=3,
                sale_date=date(2024, 10, 2),
                customer_id="C003",
                amount_cents=0,
            ),
            Sale(
                sale_id=4,
                sale_date=date(2024, 10, 3),
                customer_id="C004",
                amount_cents=400,
            ),
        ]
        original_sales = sales.copy()

        before = summarize_daily_sales(sales)
        after = summarize_daily_sales(sales)
        self.assertEqual(before, after)
        self.assertEqual(sales, original_sales)
