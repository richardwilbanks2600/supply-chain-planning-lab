"""Rolling-origin FRED driver forecasts translated into product demand."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from statistics import fmean
from typing import Literal, TypedDict

from .demand import (
    DEFAULT_LAG_MONTHS,
    PRODUCTS,
    DemandAssumptions,
    DemandRecord,
    calculate_product_demand,
)
from .forecasting import aggregate_product_demand
from .transform import ProcessedObservation


DRIVER_METHOD = "previous_month_naive"
DRIVER_METHOD_LABEL = "Previous-month naive FRED forecast"
FORECAST_ORIGIN_START = "2019-12"
FORECAST_ORIGIN_END = "2024-12"
MAX_FORECAST_HORIZON = 12
DriverStatus = Literal["known", "forecasted"]


class DriverForecastError(ValueError):
    """Raised when a FRED-informed forecast cannot be calculated safely."""


class DriverForecastRecord(TypedDict):
    """One rolling-origin product forecast with complete driver lineage."""

    forecast_origin: str
    horizon_months: int
    demand_period: str
    driver_period: str
    driver_status: DriverStatus
    driver_method: str
    actual_driver_saar_thousands: float
    driver_value_used_saar_thousands: float
    driver_error_saar_thousands: float
    product_sku: str
    product_name: str
    actual_demand_units: int
    forecast_demand_units: int
    error_units: int
    absolute_error_units: int


@dataclass(frozen=True)
class DriverForecastSummary:
    """MAE and bias for known or forecasted driver records."""

    driver_status: DriverStatus
    forecast_count: int
    mean_absolute_error: float | None
    bias: float | None


@dataclass(frozen=True)
class HorizonSummary:
    """Forecast performance at one demand horizon."""

    horizon_months: int
    driver_status: DriverStatus
    forecast_count: int
    mean_absolute_error: float | None
    bias: float | None


def calculate_driver_forecasts(
    fred_records: Sequence[ProcessedObservation],
    demand_records: Sequence[DemandRecord],
    assumptions: DemandAssumptions,
    *,
    origin_start: str = FORECAST_ORIGIN_START,
    origin_end: str = FORECAST_ORIGIN_END,
    max_horizon: int = MAX_FORECAST_HORIZON,
) -> list[DriverForecastRecord]:
    """Run a revised-history backtest from successive FRED forecast origins."""

    _parse_period(origin_start)
    _parse_period(origin_end)
    if origin_start > origin_end:
        raise DriverForecastError("Forecast origin start must not exceed end.")
    if max_horizon < 1:
        raise DriverForecastError("Forecast horizon must be at least one month.")

    driver_values = {record["period"]: record["value"] for record in fred_records}
    actual_demand = {
        (record["period"], record["product_sku"]): record["actual_units"]
        for record in aggregate_product_demand(demand_records)
    }
    records: list[DriverForecastRecord] = []
    for origin in _month_range(origin_start, origin_end):
        origin_driver = driver_values.get(origin)
        if origin_driver is None:
            raise DriverForecastError(
                f"FRED observation for forecast origin {origin} is unavailable."
            )
        for horizon in range(1, max_horizon + 1):
            demand_period = _shift_month(origin, horizon)
            driver_period = _shift_month(demand_period, -DEFAULT_LAG_MONTHS)
            actual_driver = driver_values.get(driver_period)
            if actual_driver is None:
                raise DriverForecastError(
                    f"Actual FRED driver for {driver_period} is unavailable."
                )
            driver_status: DriverStatus = (
                "known" if driver_period <= origin else "forecasted"
            )
            driver_value_used = (
                actual_driver if driver_status == "known" else origin_driver
            )
            forecast_products = calculate_product_demand(
                driver_value_used, assumptions
            )
            for product_sku, product_name in PRODUCTS.items():
                actual_units = actual_demand.get((demand_period, product_sku))
                if actual_units is None:
                    raise DriverForecastError(
                        f"Actual demand for {demand_period}/{product_sku} is unavailable."
                    )
                forecast_units = forecast_products[product_sku]
                error = actual_units - forecast_units
                records.append(
                    DriverForecastRecord(
                        forecast_origin=origin,
                        horizon_months=horizon,
                        demand_period=demand_period,
                        driver_period=driver_period,
                        driver_status=driver_status,
                        driver_method=(
                            "observed FRED value"
                            if driver_status == "known"
                            else DRIVER_METHOD
                        ),
                        actual_driver_saar_thousands=actual_driver,
                        driver_value_used_saar_thousands=driver_value_used,
                        driver_error_saar_thousands=(
                            actual_driver - driver_value_used
                        ),
                        product_sku=product_sku,
                        product_name=product_name,
                        actual_demand_units=actual_units,
                        forecast_demand_units=forecast_units,
                        error_units=error,
                        absolute_error_units=abs(error),
                    )
                )
    return records


def summarize_driver_status(
    records: Sequence[DriverForecastRecord], driver_status: DriverStatus
) -> DriverForecastSummary:
    """Calculate performance for known or forecasted driver records."""

    selected = [
        record for record in records if record["driver_status"] == driver_status
    ]
    if not selected:
        return DriverForecastSummary(driver_status, 0, None, None)
    return DriverForecastSummary(
        driver_status=driver_status,
        forecast_count=len(selected),
        mean_absolute_error=fmean(
            record["absolute_error_units"] for record in selected
        ),
        bias=fmean(record["error_units"] for record in selected),
    )


def summarize_horizons(
    records: Sequence[DriverForecastRecord],
) -> list[HorizonSummary]:
    """Calculate MAE and bias for each approved demand horizon."""

    summaries: list[HorizonSummary] = []
    for horizon in sorted({record["horizon_months"] for record in records}):
        selected = [
            record for record in records if record["horizon_months"] == horizon
        ]
        status = selected[0]["driver_status"]
        summaries.append(
            HorizonSummary(
                horizon_months=horizon,
                driver_status=status,
                forecast_count=len(selected),
                mean_absolute_error=fmean(
                    record["absolute_error_units"] for record in selected
                ),
                bias=fmean(record["error_units"] for record in selected),
            )
        )
    return summaries


def filter_driver_forecasts(
    records: Sequence[DriverForecastRecord],
    *,
    product_sku: str | None = None,
    horizon_months: int | None = None,
    driver_status: DriverStatus | None = None,
) -> list[DriverForecastRecord]:
    """Select driver forecast details in stable rolling-origin order."""

    if product_sku is not None and product_sku not in PRODUCTS:
        raise DriverForecastError(f"Unknown product SKU {product_sku!r}.")
    if horizon_months is not None and horizon_months < 1:
        raise DriverForecastError("Forecast horizon must be at least one month.")
    return sorted(
        (
            record
            for record in records
            if (product_sku is None or record["product_sku"] == product_sku)
            and (
                horizon_months is None
                or record["horizon_months"] == horizon_months
            )
            and (
                driver_status is None
                or record["driver_status"] == driver_status
            )
        ),
        key=lambda record: (
            record["forecast_origin"],
            record["horizon_months"],
            record["product_sku"],
        ),
    )


def forecast_origins() -> tuple[str, ...]:
    """Return the approved historical forecast origins."""

    return _month_range(FORECAST_ORIGIN_START, FORECAST_ORIGIN_END)


def _month_range(start: str, end: str) -> tuple[str, ...]:
    """Return all canonical months in an inclusive range."""

    months: list[str] = []
    current = start
    while current <= end:
        months.append(current)
        current = _shift_month(current, 1)
    return tuple(months)


def _parse_period(value: str) -> date:
    """Parse one canonical month."""

    try:
        parsed = date.fromisoformat(f"{value}-01")
    except ValueError as exc:
        raise DriverForecastError(
            f"Invalid period {value!r}; expected YYYY-MM."
        ) from exc
    if parsed.strftime("%Y-%m") != value:
        raise DriverForecastError(f"Invalid period {value!r}; expected YYYY-MM.")
    return parsed


def _shift_month(period: str, months: int) -> str:
    """Shift a canonical period by a signed number of months."""

    parsed = _parse_period(period)
    month_index = parsed.year * 12 + parsed.month - 1 + months
    year, zero_based_month = divmod(month_index, 12)
    return f"{year:04d}-{zero_based_month + 1:02d}"
