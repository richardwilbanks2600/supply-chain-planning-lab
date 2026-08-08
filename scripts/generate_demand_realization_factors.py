"""Generate the committed fictional demand-realization factor dataset once."""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path
import random


START_PERIOD = "2000-04"
END_PERIOD = "2026-02"
SEED = 7970
PRODUCT_SEASONAL_FACTORS = {
    "WIN-2436": (0.96, 0.97, 0.99, 1.02, 1.04, 1.05, 1.04, 1.02, 1.00, 0.99, 0.97, 0.95),
    "WIN-3648": (0.95, 0.96, 0.98, 1.01, 1.04, 1.06, 1.05, 1.03, 1.01, 0.99, 0.96, 0.94),
    "DOOR-3680": (0.98, 0.98, 0.99, 1.00, 1.01, 1.01, 1.00, 1.02, 1.04, 1.05, 1.02, 0.99),
}
OUTPUT_PATH = (
    Path(__file__).parents[1]
    / "src"
    / "supply_chain_planning_lab"
    / "resources"
    / "demand_realization_factors.csv"
)
FIELDS = (
    "period",
    "product_sku",
    "company_variation_factor",
    "product_seasonal_factor",
    "product_variation_factor",
    "unusual_event_factor",
    "realization_factor",
    "variation_type",
)


def _periods(start: str, end: str) -> list[str]:
    """Return inclusive monthly period labels."""

    year, month = (int(part) for part in start.split("-"))
    end_year, end_month = (int(part) for part in end.split("-"))
    values = []
    while (year, month) <= (end_year, end_month):
        values.append(f"{year:04d}-{month:02d}")
        month += 1
        if month == 13:
            year += 1
            month = 1
    return values


def generate_rows() -> list[dict[str, str]]:
    """Build fixed factors with typical and occasional unusual variation."""

    rng = random.Random(SEED)
    rows = []
    for period in _periods(START_PERIOD, END_PERIOD):
        month = date.fromisoformat(f"{period}-01").month
        company_factor = rng.triangular(0.90, 1.10, 1.00)
        unusual = rng.random() < 0.04
        event_factor = rng.choice((0.82, 0.85, 1.15, 1.18)) if unusual else 1.00
        for product_sku, seasonal_values in PRODUCT_SEASONAL_FACTORS.items():
            product_factor = rng.uniform(0.98, 1.02)
            seasonal_factor = seasonal_values[month - 1]
            combined = company_factor * seasonal_factor * product_factor * event_factor
            realization_factor = min(1.25, max(0.75, combined))
            rows.append(
                {
                    "period": period,
                    "product_sku": product_sku,
                    "company_variation_factor": f"{company_factor:.4f}",
                    "product_seasonal_factor": f"{seasonal_factor:.4f}",
                    "product_variation_factor": f"{product_factor:.4f}",
                    "unusual_event_factor": f"{event_factor:.4f}",
                    "realization_factor": f"{realization_factor:.4f}",
                    "variation_type": "unusual" if unusual else "typical",
                }
            )
    return rows


def main() -> None:
    """Write the reproducible factor rows to the packaged resource path."""

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(generate_rows())


if __name__ == "__main__":
    main()
