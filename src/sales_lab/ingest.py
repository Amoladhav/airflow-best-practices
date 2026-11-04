"""Read sales csv input and validate its structure."""

import csv
from typing import TextIO

from sales_lab.transform import Sale, transform_batch

EXPECTED_HEADER = ["sale_id", "sale_date", "customer_id", "amount"]


def read_sales_csv(stream: TextIO) -> list[Sale]:
    """Read a CSV stream and retrun a fully validated sales batch

    Require the exact header and four fields per record.
    Accept header-only input; reject empty or malformed input.
    Leave stream ownership with the caller.
    """
    rows: list[dict[str, str]] = []

    try:
        reader = csv.reader(stream, strict=True)
        header = next(reader, None)
        if header != EXPECTED_HEADER:
            raise ValueError(
                f"CSV header does not match expected format: {EXPECTED_HEADER}"
            )

        for record_number, values in enumerate(reader, start=2):
            if len(values) != len(EXPECTED_HEADER):
                raise ValueError(
                    f"CSV record {record_number} expected "
                    f"{len(EXPECTED_HEADER)} fields, got {len(values)}"
                )
            rows.append(dict(zip(EXPECTED_HEADER, values, strict=True)))
    except csv.Error as exc:
        raise ValueError("malformed sales csv") from exc

    return transform_batch(rows)
