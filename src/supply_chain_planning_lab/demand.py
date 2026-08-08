"""Convert a fixed FRED snapshot into an inspectable demand scenario."""

from collections.abc import Mapping, Sequence
import csv
from dataclasses import dataclass
from datetime import date
import math
from pathlib import Path
from typing import TypedDict

from .inspection import ProcessedDataError, inspect_quality, read_processed_csv
from .transform import ProcessedObservation


FRED_SNAPSHOT_PATH = (
    Path(__file__).with_name("resources") / "fred_permit_2000_2025.csv"
)
REALIZATION_FACTOR_PATH = (
    Path(__file__).with_name("resources") / "demand_realization_factors.csv"
)
SOURCE_START_PERIOD = "2000-01"
SOURCE_END_PERIOD = "2025-12"
DEMAND_END_PERIOD = "2025-12"
DEFAULT_LAG_MONTHS = 3
DEFAULT_MARKET_SHARE_PERCENT = 0.10
REALIZATION_START_PERIOD = "2000-04"
REALIZATION_END_PERIOD = "2026-02"
REALIZATION_FACTOR_FIELDS = (
    "period",
    "product_sku",
    "company_variation_factor",
    "product_seasonal_factor",
    "product_variation_factor",
    "unusual_event_factor",
    "realization_factor",
    "variation_type",
)
DEMAND_FIELDS = (
    "period",
    "fred_period",
    "fred_value_saar_thousands",
    "monthly_housing_pace",
    "company_market_share_percent",
    "customer",
    "customer_type",
    "customer_allocation_percent",
    "product_sku",
    "product_name",
    "units_per_home",
    "fred_expected_demand_units",
    "company_variation_factor",
    "product_seasonal_factor",
    "product_variation_factor",
    "unusual_event_factor",
    "realization_factor",
    "variation_type",
    "demand_units",
    "unit",
)

CUSTOMERS = {
    "Building Houses Company": "builder",
    "Building Supply Company": "distributor",
    "Building Remodeler": "remodeler",
}
PRODUCTS = {
    "WIN-2436": "24 x 36 Vinyl Window",
    "WIN-3648": "36 x 48 Vinyl Window",
    "DOOR-3680": "36 x 80 Insulated Exterior Door",
}
DEFAULT_CUSTOMER_ALLOCATIONS = {
    "Building Houses Company": 0.50,
    "Building Supply Company": 0.30,
    "Building Remodeler": 0.20,
}
DEFAULT_UNITS_PER_HOME = {
    "WIN-2436": 6.0,
    "WIN-3648": 4.0,
    "DOOR-3680": 1.0,
}


class DemandDataError(ValueError):
    """Raised when source data or scenario assumptions are invalid."""


class DemandRecord(TypedDict):
    """One derived customer-product-month record with source lineage."""

    period: str
    fred_period: str
    fred_value_saar_thousands: float
    monthly_housing_pace: float
    company_market_share_percent: float
    customer: str
    customer_type: str
    customer_allocation_percent: float
    product_sku: str
    product_name: str
    units_per_home: float
    fred_expected_demand_units: int
    company_variation_factor: float
    product_seasonal_factor: float
    product_variation_factor: float
    unusual_event_factor: float
    realization_factor: float
    variation_type: str
    demand_units: int
    unit: str


class DemandRealizationFactor(TypedDict):
    """One fixed product-month factor that separates demand from FRED expectation."""

    period: str
    product_sku: str
    company_variation_factor: float
    product_seasonal_factor: float
    product_variation_factor: float
    unusual_event_factor: float
    realization_factor: float
    variation_type: str


@dataclass(frozen=True)
class DemandAssumptions:
    """Visible business assumptions used to translate market pace into demand."""

    market_share_percent: float
    customer_allocations: Mapping[str, float]
    units_per_home: Mapping[str, float]

    def __post_init__(self) -> None:
        """Reject incomplete or mathematically unsafe assumptions."""

        if not math.isfinite(self.market_share_percent):
            raise DemandDataError("Company market share must be finite.")
        if not 0 <= self.market_share_percent <= 100:
            raise DemandDataError(
                "Company market share must be between 0 and 100 percent."
            )
        if set(self.customer_allocations) != set(CUSTOMERS):
            raise DemandDataError("Customer allocations must cover every customer.")
        allocations = tuple(self.customer_allocations.values())
        if any(not math.isfinite(value) or value < 0 for value in allocations):
            raise DemandDataError("Customer allocations must be finite and nonnegative.")
        if not math.isclose(sum(allocations), 1.0, abs_tol=1e-9):
            raise DemandDataError("Customer allocations must total 100 percent.")
        if set(self.units_per_home) != set(PRODUCTS):
            raise DemandDataError("Units per home must cover every product.")
        if any(
            not math.isfinite(value) or value < 0
            for value in self.units_per_home.values()
        ):
            raise DemandDataError("Product units per home must be finite and nonnegative.")


@dataclass(frozen=True)
class DemandSummary:
    """Additive measures for a selected set of demand records."""

    record_count: int
    fred_expected_demand_units: int
    demand_units: int


def default_assumptions() -> DemandAssumptions:
    """Return a new copy of the approved default scenario assumptions."""

    return DemandAssumptions(
        market_share_percent=DEFAULT_MARKET_SHARE_PERCENT,
        customer_allocations=dict(DEFAULT_CUSTOMER_ALLOCATIONS),
        units_per_home=dict(DEFAULT_UNITS_PER_HOME),
    )


def load_fred_snapshot() -> list[ProcessedObservation]:
    """Load and validate the fixed 2000-2025 FRED PERMIT snapshot."""

    try:
        records = read_processed_csv(FRED_SNAPSHOT_PATH)
    except ProcessedDataError as exc:
        raise DemandDataError(f"Invalid packaged FRED snapshot: {exc}") from exc
    report = inspect_quality(records)
    if report.status != "PASS":
        raise DemandDataError(
            f"Packaged FRED snapshot failed quality inspection: {report.status}."
        )
    if (
        len(records) != 312
        or report.first_period != SOURCE_START_PERIOD
        or report.last_period != SOURCE_END_PERIOD
    ):
        raise DemandDataError(
            "Packaged FRED snapshot must contain all 312 months from "
            f"{SOURCE_START_PERIOD} through {SOURCE_END_PERIOD}."
        )
    return records


def load_realization_factors() -> list[DemandRealizationFactor]:
    """Load and validate the committed fictional product-month factors."""

    try:
        with REALIZATION_FACTOR_PATH.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            if tuple(reader.fieldnames or ()) != REALIZATION_FACTOR_FIELDS:
                raise DemandDataError(
                    "Demand realization factors have an unexpected header."
                )
            source_rows = list(reader)
    except OSError as exc:
        raise DemandDataError(
            f"Could not read packaged demand realization factors: {exc}"
        ) from exc

    records: list[DemandRealizationFactor] = []
    observed_keys: set[tuple[str, str]] = set()
    for row_number, row in enumerate(source_rows, start=2):
        period = row["period"]
        product_sku = row["product_sku"]
        _parse_period(period)
        if product_sku not in PRODUCTS:
            raise DemandDataError(
                f"Demand realization factor row {row_number} has an unknown product."
            )
        key = (period, product_sku)
        if key in observed_keys:
            raise DemandDataError(
                f"Demand realization factors contain duplicate key {key!r}."
            )
        observed_keys.add(key)
        try:
            numeric = {
                field: float(row[field])
                for field in REALIZATION_FACTOR_FIELDS[2:-1]
            }
        except ValueError as exc:
            raise DemandDataError(
                f"Demand realization factor row {row_number} contains invalid numbers."
            ) from exc
        if any(not math.isfinite(value) or value <= 0 for value in numeric.values()):
            raise DemandDataError(
                f"Demand realization factor row {row_number} must contain positive finite factors."
            )
        if not 0.75 <= numeric["realization_factor"] <= 1.25:
            raise DemandDataError(
                f"Demand realization factor row {row_number} exceeds the approved range."
            )
        combined = (
            numeric["company_variation_factor"]
            * numeric["product_seasonal_factor"]
            * numeric["product_variation_factor"]
            * numeric["unusual_event_factor"]
        )
        bounded_combined = min(1.25, max(0.75, combined))
        if not math.isclose(
            numeric["realization_factor"], bounded_combined, abs_tol=0.0002
        ):
            raise DemandDataError(
                f"Demand realization factor row {row_number} does not match its components."
            )
        if row["variation_type"] not in {"typical", "unusual"}:
            raise DemandDataError(
                f"Demand realization factor row {row_number} has an invalid variation type."
            )
        expected_type = (
            "typical"
            if math.isclose(numeric["unusual_event_factor"], 1.0)
            else "unusual"
        )
        if row["variation_type"] != expected_type:
            raise DemandDataError(
                f"Demand realization factor row {row_number} has inconsistent variation labels."
            )
        records.append(
            DemandRealizationFactor(
                period=period,
                product_sku=product_sku,
                company_variation_factor=numeric["company_variation_factor"],
                product_seasonal_factor=numeric["product_seasonal_factor"],
                product_variation_factor=numeric["product_variation_factor"],
                unusual_event_factor=numeric["unusual_event_factor"],
                realization_factor=numeric["realization_factor"],
                variation_type=row["variation_type"],
            )
        )

    expected_keys = {
        (period, product_sku)
        for period in _period_range(REALIZATION_START_PERIOD, REALIZATION_END_PERIOD)
        for product_sku in PRODUCTS
    }
    if observed_keys != expected_keys:
        raise DemandDataError(
            "Packaged demand realization factors must cover every product-month "
            f"from {REALIZATION_START_PERIOD} through {REALIZATION_END_PERIOD}."
        )
    return records


def load_default_demand() -> list[DemandRecord]:
    """Build the reproducible default scenario from the fixed FRED snapshot."""

    return generate_demand(load_fred_snapshot(), default_assumptions())


def calculate_expected_product_demand(
    fred_value_saar_thousands: float,
    assumptions: DemandAssumptions,
) -> dict[str, int]:
    """Translate one FRED pace value into expected whole-unit product demand."""

    if (
        not math.isfinite(fred_value_saar_thousands)
        or fred_value_saar_thousands < 0
    ):
        raise DemandDataError("FRED pace value must be finite and nonnegative.")
    monthly_pace = fred_value_saar_thousands * 1_000 / 12
    addressable_homes = monthly_pace * assumptions.market_share_percent / 100
    return {
        product_sku: round(
            addressable_homes * assumptions.units_per_home[product_sku]
        )
        for product_sku in PRODUCTS
    }


def generate_demand(
    fred_records: Sequence[ProcessedObservation],
    assumptions: DemandAssumptions,
    *,
    lag_months: int = DEFAULT_LAG_MONTHS,
    demand_end_period: str = DEMAND_END_PERIOD,
) -> list[DemandRecord]:
    """Translate FRED expectation and fixed variation into realized demand."""

    if lag_months < 0:
        raise DemandDataError("Demand lag cannot be negative.")
    _parse_period(demand_end_period)
    realization_factors = {
        (record["period"], record["product_sku"]): record
        for record in load_realization_factors()
    }
    records: list[DemandRecord] = []
    for fred_record in sorted(fred_records, key=lambda record: record["period"]):
        demand_period = _add_months(fred_record["period"], lag_months)
        if demand_period > demand_end_period:
            continue
        monthly_pace = fred_record["value"] * 1_000 / 12
        expected_product_totals = calculate_expected_product_demand(
            fred_record["value"], assumptions
        )
        for product_sku, product_name in PRODUCTS.items():
            units_per_home = assumptions.units_per_home[product_sku]
            factor = realization_factors.get((demand_period, product_sku))
            if factor is None:
                raise DemandDataError(
                    "No static demand realization factor exists for "
                    f"{demand_period} and {product_sku}."
                )
            expected_customer_units = _allocate_units(
                expected_product_totals[product_sku],
                assumptions.customer_allocations,
            )
            realized_product_total = round(
                expected_product_totals[product_sku] * factor["realization_factor"]
            )
            realized_customer_units = _allocate_units(
                realized_product_total, assumptions.customer_allocations
            )
            for customer, customer_type in CUSTOMERS.items():
                records.append(
                    DemandRecord(
                        period=demand_period,
                        fred_period=fred_record["period"],
                        fred_value_saar_thousands=fred_record["value"],
                        monthly_housing_pace=monthly_pace,
                        company_market_share_percent=assumptions.market_share_percent,
                        customer=customer,
                        customer_type=customer_type,
                        customer_allocation_percent=(
                            assumptions.customer_allocations[customer] * 100
                        ),
                        product_sku=product_sku,
                        product_name=product_name,
                        units_per_home=units_per_home,
                        fred_expected_demand_units=expected_customer_units[customer],
                        company_variation_factor=factor["company_variation_factor"],
                        product_seasonal_factor=factor["product_seasonal_factor"],
                        product_variation_factor=factor["product_variation_factor"],
                        unusual_event_factor=factor["unusual_event_factor"],
                        realization_factor=factor["realization_factor"],
                        variation_type=factor["variation_type"],
                        demand_units=realized_customer_units[customer],
                        unit="finished_units",
                    )
                )
    return records


def filter_demand(
    records: Sequence[DemandRecord],
    *,
    start_period: str | None = None,
    end_period: str | None = None,
    customer: str | None = None,
    product_sku: str | None = None,
) -> list[DemandRecord]:
    """Apply inclusive scenario filters in stable chronological order."""

    if start_period is not None:
        _parse_period(start_period)
    if end_period is not None:
        _parse_period(end_period)
    if start_period and end_period and start_period > end_period:
        raise DemandDataError("Start period must not be later than end period.")
    if customer is not None and customer not in CUSTOMERS:
        raise DemandDataError(f"Unknown customer {customer!r}.")
    if product_sku is not None and product_sku not in PRODUCTS:
        raise DemandDataError(f"Unknown product SKU {product_sku!r}.")

    return sorted(
        (
            record
            for record in records
            if (start_period is None or record["period"] >= start_period)
            and (end_period is None or record["period"] <= end_period)
            and (customer is None or record["customer"] == customer)
            and (product_sku is None or record["product_sku"] == product_sku)
        ),
        key=lambda record: (
            record["period"],
            record["customer"],
            record["product_sku"],
        ),
    )


def summarize_demand(records: Sequence[DemandRecord]) -> DemandSummary:
    """Sum FRED-driven expectation and realized fictional demand."""

    return DemandSummary(
        record_count=len(records),
        fred_expected_demand_units=sum(
            record["fred_expected_demand_units"] for record in records
        ),
        demand_units=sum(record["demand_units"] for record in records),
    )


def monthly_demand(records: Sequence[DemandRecord]) -> list[dict[str, str | int]]:
    """Aggregate selected realized demand by requested ship month."""

    totals: dict[str, int] = {}
    for record in records:
        totals[record["period"]] = totals.get(record["period"], 0) + record[
            "demand_units"
        ]
    return [
        {"period": period, "demand_units": units}
        for period, units in sorted(totals.items())
    ]


def monthly_demand_comparison(
    records: Sequence[DemandRecord],
) -> list[dict[str, str | int]]:
    """Aggregate FRED-driven expectation and realized demand by month."""

    totals: dict[str, dict[str, int]] = {}
    for record in records:
        period_totals = totals.setdefault(
            record["period"],
            {"fred_expected_demand_units": 0, "realized_demand_units": 0},
        )
        period_totals["fred_expected_demand_units"] += record[
            "fred_expected_demand_units"
        ]
        period_totals["realized_demand_units"] += record["demand_units"]
    return [
        {"period": period, **values}
        for period, values in sorted(totals.items())
    ]


def _allocate_units(
    total_units: int, allocations: Mapping[str, float]
) -> dict[str, int]:
    """Allocate whole units proportionally while preserving the product total."""

    exact = {customer: total_units * allocations[customer] for customer in CUSTOMERS}
    allocated = {customer: math.floor(value) for customer, value in exact.items()}
    remainder = total_units - sum(allocated.values())
    ranked = sorted(
        CUSTOMERS,
        key=lambda customer: exact[customer] - allocated[customer],
        reverse=True,
    )
    for customer in ranked[:remainder]:
        allocated[customer] += 1
    return allocated


def _parse_period(value: str) -> date:
    """Parse one canonical YYYY-MM period."""

    try:
        parsed = date.fromisoformat(f"{value}-01")
    except ValueError as exc:
        raise DemandDataError(f"Invalid period {value!r}; expected YYYY-MM") from exc
    if parsed.strftime("%Y-%m") != value:
        raise DemandDataError(f"Invalid period {value!r}; expected YYYY-MM")
    return parsed


def _add_months(period: str, months: int) -> str:
    """Shift a canonical month forward by a nonnegative number of months."""

    parsed = _parse_period(period)
    month_index = parsed.year * 12 + parsed.month - 1 + months
    year, zero_based_month = divmod(month_index, 12)
    return f"{year:04d}-{zero_based_month + 1:02d}"


def _period_range(start_period: str, end_period: str) -> list[str]:
    """Return inclusive canonical months between two period labels."""

    _parse_period(start_period)
    _parse_period(end_period)
    if start_period > end_period:
        raise DemandDataError("Period range start must not exceed its end.")
    periods = []
    current = start_period
    while current <= end_period:
        periods.append(current)
        current = _add_months(current, 1)
    return periods
