import os
import unittest
from pathlib import Path
from unittest.mock import patch

from sales_lab.config import get_sales_paths


class GetSalesPathsTest(unittest.TestCase):
    def test_returns_configured_paths(self):
        environment = {
            "SALES_CSV_PATH": "sample_data/sales.csv",
            "SALES_DB_PATH": "sample_data/sales.sqlite",
        }

        with patch.dict(os.environ, environment, clear=True):
            result = get_sales_paths()

        self.assertEqual(
            result, (Path("sample_data/sales.csv"), Path("sample_data/sales.sqlite"))
        )

    def test_reads_current_configuration_on_each_call(self):
        for stage in ("dev", "test"):
            with self.subTest(stage=stage):
                environment = {
                    "SALES_CSV_PATH": f"data/{stage}/sales.csv",
                    "SALES_DB_PATH": f"data/{stage}/sales.sqlite",
                }

                with patch.dict(os.environ, environment, clear=True):
                    result = get_sales_paths()
                self.assertEqual(
                    result,
                    (
                        Path(f"data/{stage}/sales.csv"),
                        Path(f"data/{stage}/sales.sqlite"),
                    ),
                )

    def test_rejects_missing_or_blank_configuration(self):
        for name in ("SALES_CSV_PATH", "SALES_DB_PATH"):
            for value in (None, "", "   "):
                with self.subTest(name=name, value=value):
                    environment = {
                        "SALES_CSV_PATH": "sample_data/sales.csv",
                        "SALES_DB_PATH": "data/dev/sales.sqlite",
                    }

                    if value is None:
                        del environment[name]
                    else:
                        environment[name] = value

                    with patch.dict(os.environ, environment, clear=True):
                        with self.assertRaises(ValueError):
                            get_sales_paths()
