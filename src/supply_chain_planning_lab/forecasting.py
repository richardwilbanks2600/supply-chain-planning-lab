"""Explainable baseline forecasts for derived internal demand."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from statistics import fmean
from typing import Literal, TypedDict

from .demand import DemandRecord, PRODUCTS


ForecastMethod = Literal[
    "previous_month",
    "seasonal_naive",
    "trailing_3_average",
]
METHOD_LABELS: dict[ForecastMethod, str] = {
    "previous_month": "Previous month",
    "seasonal_naive": "Same month last year",
    "trailing_3_average": "Trailing 3-month average",
}
PRIMARY_METHOD: ForecastMethod = "seasonal_naive"
EVALUATION_START_PERIOD = "2020-01"
EVALUATION_END_PERIOD = "2025-12"


class ForecastError(ValueError):
    """Raised when a baseline forecast cannot be calculated safely."""


class ProductDemandRecord(TypedDict):
    """Monthly realized demand aggregated across customers for one product."""

    period: str
    product_sku: str
    product_name: str
    actual_units: int


class ForecastRecord(TypedDict):
    """One baseline forecast and its signed error."""

    period: str
    product_sku: str
    product_name: str
    method: ForecastMethod
    method_label: str
    actual_units: int
    forecast_units: float
    error_units: float
    absolute_error_units: float


@dataclass(frozen=True)
class ForecastSummary:
    """Transparent performance measures for one forecast method."""

    method: ForecastMethod
    method_label: str
    forecast_count: int
    mean_absolute_error: float | None
    bias: float | None


def aggregate_product_demand(
    records: Sequence[DemandRecord],
) -> list[ProductDemandRecord]:
    """Sum customer demand to the approved product-month forecast grain."""

    totals: dict[tuple[str, str], int] = {}
    for record in records:
        key = (record["period"], record["product_sku"])
        totals[key] = totals.get(key, 0) + record["demand_units"]
    return [
        ProductDemandRecord(
            period=period,
            product_sku=product_sku,
            product_name=PRODUCTS[product_sku],
            actual_units=units,
        )
        for (period, product_sku), units in sorted(totals.items())
    ]


def calculate_forecasts(
    demand_records: Sequence[DemandRecord],
    method: ForecastMethod,
    *,
    start_period: str = EVALUATION_START_PERIOD,
    end_period: str = EVALUATION_END_PERIOD,
) -> list[ForecastRecord]:
    """Calculate one-month-ahead forecasts using prior realized demand only."""

    if method not in METHOD_LABELS:
        raise ForecastError(f"Unknown forecast method {method!r}.")
    _parse_period(start_period)
    _parse_period(end_period)
    if start_period > end_period:
        raise ForecastError("Forecast start period must not exceed end period.")

    product_records = aggregate_product_demand(demand_records)
    actuals = {
        (record["period"], record["product_sku"]): record["actual_units"]
        for record in product_records
    }
    forecasts: list[ForecastRecord] = []
    for record in product_records:
        period = record["period"]
        if period < start_period or period > end_period:
            continue
        history_periods = _history_periods(period, method)
        history_values = [
            actuals.get((history_period, record["product_sku"]))
            for history_period in history_periods
        ]
        if any(value is None for value in history_values):
            continue
        trusted_history = [float(value) for value in history_values if value is not None]
        forecast = (
            fmean(trusted_history)
            if method == "trailing_3_average"
            else trusted_history[0]
        )
        error = record["actual_units"] - forecast
        forecasts.append(
            ForecastRecord(
                period=period,
                product_sku=record["product_sku"],
                product_name=record["product_name"],
                method=method,
                method_label=METHOD_LABELS[method],
                actual_units=record["actual_units"],
                forecast_units=forecast,
                error_units=error,
                absolute_error_units=abs(error),
            )
        )
    return forecasts


def summarize_forecasts(
    records: Sequence[ForecastRecord], method: ForecastMethod
) -> ForecastSummary:
    """Calculate MAE and signed mean error for one method."""

    selected = [record for record in records if record["method"] == method]
    if not selected:
        return ForecastSummary(method, METHOD_LABELS[method], 0, None, None)
    return ForecastSummary(
        method=method,
        method_label=METHOD_LABELS[method],
        forecast_count=len(selected),
        mean_absolute_error=fmean(
            record["absolute_error_units"] for record in selected
        ),
        bias=fmean(record["error_units"] for record in selected),
    )


def compare_baselines(
    demand_records: Sequence[DemandRecord],
    *,
    start_period: str = EVALUATION_START_PERIOD,
    end_period: str = EVALUATION_END_PERIOD,
) -> tuple[list[ForecastRecord], list[ForecastSummary]]:
    """Calculate all approved baselines over one common evaluation period."""

    all_records: list[ForecastRecord] = []
    summaries: list[ForecastSummary] = []
    for method in METHOD_LABELS:
        method_records = calculate_forecasts(
            demand_records,
            method,
            start_period=start_period,
            end_period=end_period,
        )
        all_records.extend(method_records)
        summaries.append(summarize_forecasts(method_records, method))
    return all_records, summaries


def filter_forecasts(
    records: Sequence[ForecastRecord],
    *,
    method: ForecastMethod | None = None,
    product_sku: str | None = None,
) -> list[ForecastRecord]:
    """Select forecast details in stable chronological order."""

    if method is not None and method not in METHOD_LABELS:
        raise ForecastError(f"Unknown forecast method {method!r}.")
    if product_sku is not None and product_sku not in PRODUCTS:
        raise ForecastError(f"Unknown product SKU {product_sku!r}.")
    return sorted(
        (
            record
            for record in records
            if (method is None or record["method"] == method)
            and (product_sku is None or record["product_sku"] == product_sku)
        ),
        key=lambda record: (
            record["period"],
            record["product_sku"],
            record["method"],
        ),
    )


def _history_periods(period: str, method: ForecastMethod) -> tuple[str, ...]:
    """Return the historical months used by one baseline calculation."""

    if method == "previous_month":
        return (_shift_month(period, -1),)
    if method == "seasonal_naive":
        return (_shift_month(period, -12),)
    return tuple(_shift_month(period, -offset) for offset in (1, 2, 3))


def _parse_period(value: str) -> date:
    """Parse one canonical month for evaluation filters."""

    try:
        parsed = date.fromisoformat(f"{value}-01")
    except ValueError as exc:
        raise ForecastError(f"Invalid period {value!r}; expected YYYY-MM.") from exc
    if parsed.strftime("%Y-%m") != value:
        raise ForecastError(f"Invalid period {value!r}; expected YYYY-MM.")
    return parsed


def _shift_month(period: str, months: int) -> str:
    """Shift a canonical period by a signed number of months."""

    parsed = _parse_period(period)
    month_index = parsed.year * 12 + parsed.month - 1 + months
    year, zero_based_month = divmod(month_index, 12)
    return f"{year:04d}-{zero_based_month + 1:02d}"
