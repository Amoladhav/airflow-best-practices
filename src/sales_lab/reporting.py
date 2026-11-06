"""Aggregate validated sales for reporting."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

from sales_lab.transform import Sale


@dataclass(frozen=True)
class DailySalesTotal:
    sale_date: date
    sale_count: int
    total_amount_cents: int


def summarize_daily_sales(sales: Iterable[Sale]) -> list[DailySalesTotal]:
    """Summarize unique, validated sales in ascending date order."""
    daily_totals: dict[date, DailySalesTotal] = {}

    for sale in sales:
        if sale.sale_date not in daily_totals:
            daily_totals[sale.sale_date] = DailySalesTotal(
                sale_date=sale.sale_date,
                sale_count=0,
                total_amount_cents=0,
            )
        daily_total = daily_totals[sale.sale_date]
        daily_totals[sale.sale_date] = DailySalesTotal(
            sale_date=daily_total.sale_date,
            sale_count=daily_total.sale_count + 1,
            total_amount_cents=daily_total.total_amount_cents + sale.amount_cents,
        )

    return sorted(daily_totals.values(), key=lambda x: x.sale_date)
