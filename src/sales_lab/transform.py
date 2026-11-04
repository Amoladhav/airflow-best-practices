"""Validate source records and normalize monetary amounts"""

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

MAX_INTEGER = 2**63 - 1


@dataclass(frozen=True)
class Sale:
    sale_id: int
    sale_date: date
    customer_id: str
    amount_cents: int


def transform_row(row: Mapping[str, str]) -> Sale:
    """Convert one source row into a validated sale.

    Raise ValueError when required fields are missing or invalid.
    Surround whitespace is ignored.
    """
    required = ["sale_id", "sale_date", "customer_id", "amount"]
    fields: dict[str, str] = {}

    for name in required:
        value = row.get(name)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{name}: expected non-empty string")
        fields[name] = value.strip()

    raw_id = fields["sale_id"]
    if not re.fullmatch(r"[0-9]{1,19}", raw_id):
        raise ValueError(f"{raw_id}: sale_id expected positive integer")
    sale_id = int(raw_id)
    if not 1 <= sale_id <= MAX_INTEGER:
        raise ValueError("sale_id: outside supported integer range")

    raw_date = fields["sale_date"]
    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", raw_date):
        raise ValueError(f"{raw_date}: sale_date expected YYYY-MM-DD")
    try:
        sale_date = date.fromisoformat(raw_date)
    except ValueError as exec:
        raise ValueError("sale_date: invalid calendar date") from exec

    raw_amount = fields["amount"]
    if not re.fullmatch(r"[0-9]{1,17}(?:\.[0-9]{1,2})?", raw_amount):
        raise ValueError(
            f"{raw_amount}: amount expected a non-negative number with atmost two decimal places"
        )
    try:
        amount_cents = int(Decimal(raw_amount) * 100)
    except ArithmeticError as exc:
        raise ValueError(f"{raw_amount}: invalid monetary value") from exc
    if amount_cents > MAX_INTEGER:
        raise ValueError(f"{amount_cents}: amount outside supported integer range")

    return Sale(
        sale_id=sale_id,
        sale_date=sale_date,
        customer_id=fields["customer_id"],
        amount_cents=amount_cents,
    )


def transform_batch(rows: Iterable[Mapping[str, str]]) -> list[Sale]:
    """Validate all rows, preserving order and rejecting duplicate sale IDs."""

    validated_sales: list[Sale] = []
    seen_ids: set[int] = set()

    for row in rows:
        sale = transform_row(row)
        if sale.sale_id in seen_ids:
            raise ValueError(f"{sale.sale_id}: duplicate sale_id")
        seen_ids.add(sale.sale_id)
        validated_sales.append(sale)

    return validated_sales
