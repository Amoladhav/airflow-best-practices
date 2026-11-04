"""Tests for sales CSV structure and validation"""

import unittest
from io import StringIO

from sales_lab.ingest import read_sales_csv

HEADER = "sale_id,sale_date,customer_id,amount\n"


class ReadSalesCsvTest(unittest.TestCase):
    def test_valid_input_returns_sales_and_leaves_stream_open(self):
        stream = StringIO(
            HEADER + "1,2024-06-01,c001,10.95\n" + "2,2024-06-02,c002,0.00\n"
        )
        sales = read_sales_csv(stream)
        self.assertEqual([sale.sale_id for sale in sales], [1, 2])
        self.assertEqual([sale.amount_cents for sale in sales], [1095, 0])
        self.assertFalse(stream.closed)

    def test_header_only_returns_empty_list(self):
        self.assertEqual(read_sales_csv(StringIO(HEADER)), [])

    def test_invalid_headers_are_rejected(self):
        headers = [
            "",
            "sale_id,sale_date,customer_id\n",
            "sale_id,sale_date,customer_id,amount,extra\n",
            "sale_id,sale_date,customer_id,customer_id\n",
            "sale_date,sale_id,customer_id,amount\n",
        ]
        for header in headers:
            with self.subTest(header=header):
                with self.assertRaisesRegex(ValueError, "header"):
                    read_sales_csv(StringIO(header))

    def test_incorrect_record_width_is_rejected(self):
        records = ["1,2026-01-01,c001\n", "1,2026-01-01,c001,10.95,extra\n"]
        for record in records:
            with self.subTest(record=record):
                with self.assertRaisesRegex(ValueError, "record 2"):
                    read_sales_csv(StringIO(HEADER + record))

    def test_malformed_csv_is_rejected(self):
        stream = StringIO(HEADER + '1,2024-06-01,"c001,10.95\n')
        with self.assertRaisesRegex(ValueError, "malformed sales csv"):
            read_sales_csv(stream)

    def test_duplicate_sale_ids_are_rejected(self):
        stream = StringIO(
            HEADER + "1,2024-06-01,c001,10.95\n" + "1,2024-06-02,c002,0.00\n"
        )
        with self.assertRaisesRegex(ValueError, "duplicate sale_id"):
            read_sales_csv(stream)

    def test_invalid_amount_is_rejected(self):
        stream = StringIO(HEADER + "1,2024-06-01,c001,-0.01\n")
        with self.assertRaisesRegex(ValueError, "amount"):
            read_sales_csv(stream)
