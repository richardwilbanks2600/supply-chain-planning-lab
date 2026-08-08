"""Command-line interface for the data workflow."""

import argparse
import logging
import math
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Sequence

from dotenv import load_dotenv

from .api import FredApiError
from .capacity import (
    DEFAULT_DOWNTIME_PERCENT,
    DEFAULT_HOURS_PER_SHIFT,
    DEFAULT_RUN_RATES,
    DEFAULT_SETUP_HOURS,
    DEFAULT_SHIFTS_PER_DAY,
    DEFAULT_WORKING_DAYS,
    WORK_CENTERS,
    CapacityPlanningError,
    CapacityPolicy,
    build_capacity_plan,
    filter_capacity_products,
    filter_work_centers,
    summarize_capacity_plan,
)
from .demand import (
    CUSTOMERS,
    DEFAULT_LAG_MONTHS,
    DEMAND_FIELDS,
    PRODUCTS,
    DemandDataError,
    default_assumptions,
    filter_demand,
    generate_demand,
    load_default_demand,
    load_fred_snapshot,
    summarize_demand,
)
from .inspection import (
    ProcessedDataError,
    filter_records,
    inspect_quality,
    read_processed_csv,
    summarize_records,
)
from .forecasting import (
    EVALUATION_END_PERIOD,
    EVALUATION_START_PERIOD,
    METHOD_LABELS,
    PRIMARY_METHOD,
    ForecastError,
    compare_baselines,
    filter_forecasts,
    summarize_forecasts,
)
from .driver_forecasting import (
    DRIVER_METHOD_LABEL,
    MAX_FORECAST_HORIZON,
    DriverForecastError,
    calculate_driver_forecasts,
    filter_driver_forecasts,
    forecast_origins,
    summarize_driver_status,
    summarize_horizons,
)
from .inventory import (
    DEFAULT_SAFETY_STOCK_PERCENT,
    DEFAULT_STARTING_INVENTORY,
    InventoryPlanningError,
    InventoryPolicy,
    build_inventory_plan,
    default_inventory_policy,
    filter_inventory_plan,
    summarize_inventory_plan,
)
from .materials import (
    COMPONENTS,
    DEFAULT_MATERIAL_INVENTORY,
    MaterialDataError,
)
from .planning_workflow import prepare_procurement_inputs
from .procurement import (
    RECEIPT_TREATMENTS,
    SAFETY_STOCK_METHODS,
    SERVICE_LEVEL_Z,
    ProcurementPlanningError,
    ProcurementPolicy,
    build_procurement_plan,
    compare_safety_stock,
    filter_procurement_plan,
    summarize_procurement_plan,
)
from .logging_config import LoggingSetupError, configure_logging
from .metadata import project_info
from .output import create_output_paths, write_processed_csv, write_raw_response
from .transform import DataTransformError
from .workflow import fetch_planning_data

SERIES_ID = "PERMIT"
DEFAULT_START_DATE = "2020-01-01"
DEFAULT_OUTPUT_DIR = Path("data")
logger = logging.getLogger(__name__)


def iso_date(value: str) -> str:
    """Validate a CLI date and return its original ISO representation."""

    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "expected an ISO date in YYYY-MM-DD format"
        ) from exc
    return value


def month_period(value: str) -> str:
    """Validate a CLI month and return its canonical representation."""

    try:
        parsed = datetime.strptime(value, "%Y-%m")
    except ValueError as exc:
        raise argparse.ArgumentTypeError("expected a month in YYYY-MM format") from exc
    if parsed.strftime("%Y-%m") != value:
        raise argparse.ArgumentTypeError("expected a month in YYYY-MM format")
    return value


def positive_integer(value: str) -> int:
    """Validate a positive integer CLI option."""

    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("expected a positive integer") from exc
    if parsed < 1:
        raise argparse.ArgumentTypeError("expected a positive integer")
    return parsed


def nonnegative_integer(value: str) -> int:
    """Validate a nonnegative whole-unit CLI option."""

    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("expected a nonnegative integer") from exc
    if parsed < 0:
        raise argparse.ArgumentTypeError("expected a nonnegative integer")
    return parsed


def percentage(value: str) -> float:
    """Validate a percentage from zero through 100."""

    try:
        parsed = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("expected a percentage") from exc
    if not 0 <= parsed <= 100:
        raise argparse.ArgumentTypeError("expected a percentage from 0 through 100")
    return parsed


def positive_number(value: str) -> float:
    """Validate a positive finite number."""

    try:
        parsed = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("expected a positive number") from exc
    if not math.isfinite(parsed) or parsed <= 0:
        raise argparse.ArgumentTypeError("expected a positive number")
    return parsed


def nonnegative_number(value: str) -> float:
    """Validate a nonnegative finite number."""

    try:
        parsed = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("expected a nonnegative number") from exc
    if not math.isfinite(parsed) or parsed < 0:
        raise argparse.ArgumentTypeError("expected a nonnegative number")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""

    parser = argparse.ArgumentParser(
        prog="planning-lab",
        description="Collect and prepare data for supply-chain planning exercises.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="write operational INFO messages to the console",
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        default=None,
        metavar="PATH",
        help="write detailed DEBUG messages to PATH",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    fetch_parser = subparsers.add_parser(
        "fetch", help="Fetch and process the FRED PERMIT series."
    )
    fetch_parser.add_argument(
        "--start-date",
        type=iso_date,
        default=DEFAULT_START_DATE,
        help=f"First observation date (default: {DEFAULT_START_DATE}).",
    )
    fetch_parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Generated-data directory (default: {DEFAULT_OUTPUT_DIR}).",
    )

    info_parser = subparsers.add_parser(
        "project-info", help="Show setup state without calling FRED."
    )
    info_parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Generated-data directory (default: {DEFAULT_OUTPUT_DIR}).",
    )

    inspect_parser = subparsers.add_parser(
        "inspect",
        help="Validate, filter, and describe a processed PERMIT CSV.",
    )
    inspect_parser.add_argument(
        "input_csv",
        type=Path,
        metavar="CSV",
        help="processed CSV file to inspect",
    )
    inspect_parser.add_argument(
        "--start-period",
        type=month_period,
        default=None,
        help="first month to include, in YYYY-MM format",
    )
    inspect_parser.add_argument(
        "--end-period",
        type=month_period,
        default=None,
        help="last month to include, in YYYY-MM format",
    )
    inspect_parser.add_argument(
        "--limit",
        type=positive_integer,
        default=None,
        help="maximum rows to list after filtering (default: all)",
    )

    demand_parser = subparsers.add_parser(
        "demand",
        help="Inspect the default FRED-driven internal-demand scenario.",
    )
    demand_parser.add_argument(
        "--start-period",
        type=month_period,
        default=None,
        help="first requested ship month to include, in YYYY-MM format",
    )
    demand_parser.add_argument(
        "--end-period",
        type=month_period,
        default=None,
        help="last requested ship month to include, in YYYY-MM format",
    )
    demand_parser.add_argument(
        "--customer",
        choices=tuple(CUSTOMERS),
        default=None,
        help="customer to include (default: all)",
    )
    demand_parser.add_argument(
        "--product",
        choices=tuple(PRODUCTS),
        default=None,
        metavar="SKU",
        help="product SKU to include (default: all)",
    )
    demand_parser.add_argument(
        "--limit",
        type=positive_integer,
        default=None,
        help="maximum rows to list after filtering (default: all)",
    )

    forecast_parser = subparsers.add_parser(
        "forecast",
        help="Compare explainable internal-demand baseline forecasts.",
    )
    forecast_parser.add_argument(
        "--method",
        choices=tuple(METHOD_LABELS),
        default=PRIMARY_METHOD,
        help=f"method to list in detail (default: {PRIMARY_METHOD})",
    )
    forecast_parser.add_argument(
        "--product",
        choices=tuple(PRODUCTS),
        default=None,
        metavar="SKU",
        help="product SKU to list (default: all)",
    )
    forecast_parser.add_argument(
        "--start-period",
        type=month_period,
        default=EVALUATION_START_PERIOD,
        help=f"first evaluation month (default: {EVALUATION_START_PERIOD})",
    )
    forecast_parser.add_argument(
        "--end-period",
        type=month_period,
        default=EVALUATION_END_PERIOD,
        help=f"last evaluation month (default: {EVALUATION_END_PERIOD})",
    )
    forecast_parser.add_argument(
        "--limit",
        type=positive_integer,
        default=None,
        help="maximum detail rows to list (default: all)",
    )

    fred_forecast_parser = subparsers.add_parser(
        "fred-forecast",
        help="Evaluate demand forecasts driven by known and forecasted FRED values.",
    )
    fred_forecast_parser.add_argument(
        "--product",
        choices=tuple(PRODUCTS),
        default=None,
        metavar="SKU",
        help="product SKU to list (default: all)",
    )
    fred_forecast_parser.add_argument(
        "--horizon",
        type=positive_integer,
        choices=range(1, MAX_FORECAST_HORIZON + 1),
        default=None,
        metavar="MONTHS",
        help=f"demand horizon to list (1-{MAX_FORECAST_HORIZON}; default: all)",
    )
    fred_forecast_parser.add_argument(
        "--limit",
        type=positive_integer,
        default=None,
        help="maximum detail rows to list (default: all)",
    )

    inventory_parser = subparsers.add_parser(
        "inventory-plan",
        help="Calculate finished-goods inventory and net production requirements.",
    )
    inventory_parser.add_argument(
        "--origin",
        choices=forecast_origins(),
        default="2024-12",
        help="historical FRED forecast origin (default: 2024-12)",
    )
    inventory_parser.add_argument(
        "--safety-stock-percent",
        type=percentage,
        default=DEFAULT_SAFETY_STOCK_PERCENT,
        help=(
            "following-month forecast held as safety stock "
            f"(default: {DEFAULT_SAFETY_STOCK_PERCENT:.0f})"
        ),
    )
    for product_sku in PRODUCTS:
        option = f"--starting-{product_sku.lower()}"
        inventory_parser.add_argument(
            option,
            type=nonnegative_integer,
            default=DEFAULT_STARTING_INVENTORY[product_sku],
            metavar="UNITS",
            help=(
                f"starting inventory for {product_sku} "
                f"(default: {DEFAULT_STARTING_INVENTORY[product_sku]})"
            ),
        )
    inventory_parser.add_argument(
        "--product",
        choices=tuple(PRODUCTS),
        default=None,
        metavar="SKU",
        help="product SKU to list (default: all)",
    )
    inventory_parser.add_argument(
        "--limit",
        type=positive_integer,
        default=None,
        help="maximum detail rows to list (default: all)",
    )

    procurement_parser = subparsers.add_parser(
        "procurement-plan",
        help="Calculate BOM, material purchasing, and supplier-risk measures.",
    )
    procurement_parser.add_argument(
        "--origin",
        choices=forecast_origins(),
        default="2024-12",
        help="historical FRED forecast origin (default: 2024-12)",
    )
    procurement_parser.add_argument(
        "--safety-method",
        choices=SAFETY_STOCK_METHODS,
        default="percentage",
        help="material safety-stock method (default: percentage)",
    )
    procurement_parser.add_argument(
        "--safety-stock-percent",
        type=percentage,
        default=25.0,
        help="following-month material requirement held (default: 25)",
    )
    procurement_parser.add_argument(
        "--service-level",
        type=float,
        choices=tuple(SERVICE_LEVEL_Z),
        default=95.0,
        help="statistical safety-stock service level (default: 95)",
    )
    procurement_parser.add_argument(
        "--receipt-treatment",
        choices=RECEIPT_TREATMENTS,
        default="full",
        help="scheduled-receipt treatment (default: full)",
    )
    for component_sku in COMPONENTS:
        procurement_parser.add_argument(
            f"--starting-{component_sku.lower()}",
            type=nonnegative_integer,
            default=DEFAULT_MATERIAL_INVENTORY[component_sku],
            metavar="UNITS",
            help=(
                f"starting material inventory for {component_sku} "
                f"(default: {DEFAULT_MATERIAL_INVENTORY[component_sku]})"
            ),
        )
    procurement_parser.add_argument(
        "--component",
        choices=tuple(COMPONENTS),
        default=None,
        metavar="SKU",
        help="component SKU to list (default: all)",
    )
    procurement_parser.add_argument(
        "--limit",
        type=positive_integer,
        default=None,
        help="maximum detail rows to list (default: all)",
    )

    capacity_parser = subparsers.add_parser(
        "capacity-plan",
        help="Compare production load with monthly work-center capacity.",
    )
    capacity_parser.add_argument(
        "--origin",
        choices=forecast_origins(),
        default="2024-12",
        help="historical FRED forecast origin (default: 2024-12)",
    )
    capacity_parser.add_argument(
        "--working-days",
        type=positive_integer,
        default=DEFAULT_WORKING_DAYS,
        help=f"working days per month (default: {DEFAULT_WORKING_DAYS})",
    )
    capacity_parser.add_argument(
        "--shifts-per-day",
        type=int,
        choices=(1, 2, 3),
        default=DEFAULT_SHIFTS_PER_DAY,
        help=f"shifts per working day (default: {DEFAULT_SHIFTS_PER_DAY})",
    )
    capacity_parser.add_argument(
        "--hours-per-shift",
        type=positive_number,
        default=DEFAULT_HOURS_PER_SHIFT,
        help=f"hours per shift (default: {DEFAULT_HOURS_PER_SHIFT:g})",
    )
    capacity_parser.add_argument(
        "--downtime-percent",
        type=percentage,
        default=DEFAULT_DOWNTIME_PERCENT,
        help=f"planned regular-hour downtime (default: {DEFAULT_DOWNTIME_PERCENT:g})",
    )
    capacity_parser.add_argument(
        "--setup-hours",
        type=nonnegative_number,
        default=DEFAULT_SETUP_HOURS,
        help=f"setup hours per active product (default: {DEFAULT_SETUP_HOURS:g})",
    )
    capacity_parser.add_argument(
        "--window-overtime",
        type=nonnegative_number,
        default=0.0,
        help="Window Assembly overtime hours per month (default: 0)",
    )
    capacity_parser.add_argument(
        "--door-overtime",
        type=nonnegative_number,
        default=0.0,
        help="Door Assembly overtime hours per month (default: 0)",
    )
    for product_sku in PRODUCTS:
        capacity_parser.add_argument(
            f"--rate-{product_sku.lower()}",
            type=positive_number,
            default=DEFAULT_RUN_RATES[product_sku],
            metavar="UNITS_PER_HOUR",
            help=(
                f"run rate for {product_sku} "
                f"(default: {DEFAULT_RUN_RATES[product_sku]:g})"
            ),
        )
    capacity_parser.add_argument(
        "--work-center",
        choices=tuple(WORK_CENTERS),
        default=None,
        help="work center to list (default: all)",
    )
    capacity_parser.add_argument(
        "--product",
        choices=tuple(PRODUCTS),
        default=None,
        metavar="SKU",
        help="product to list (default: all)",
    )
    capacity_parser.add_argument(
        "--limit",
        type=positive_integer,
        default=None,
        help="maximum rows in each detail table (default: all)",
    )

    return parser


def run_fetch(*, start_date: str, output_dir: Path, api_key: str) -> int:
    """Run the live FRED-to-files workflow."""

    paths = create_output_paths(output_dir)

    try:
        result = fetch_planning_data(
            api_key=api_key,
            series_id=SERIES_ID,
            observation_start=start_date,
            preserve_raw=lambda response: write_raw_response(
                paths.raw, response.raw_text
            ),
        )
        write_processed_csv(paths.processed, result.records)
    except (FredApiError, DataTransformError, OSError) as exc:
        logger.error("Fetch workflow failed: %s", exc)
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    logger.info("Saved processed observations to %s.", paths.processed)
    print(f"Fetched FRED series {SERIES_ID}.")
    print(f"Processed {len(result.records)} valid observations.")
    print(f"Skipped {result.skipped_missing} missing observations.")
    if result.records:
        print(
            f"Period: {result.records[0]['period']} "
            f"through {result.records[-1]['period']}"
        )
    print(f"Raw: {paths.raw}")
    print(f"Processed: {paths.processed}")
    return 0


def run_inspect(
    *,
    input_csv: Path,
    start_period: str | None,
    end_period: str | None,
    limit: int | None,
) -> int:
    """Validate and describe one previously processed CSV file."""

    try:
        records = read_processed_csv(input_csv)
        report = inspect_quality(records)
        selected = filter_records(
            records,
            start_period=start_period,
            end_period=end_period,
        )
    except (OSError, UnicodeError, ProcessedDataError) as exc:
        logger.error("Processed-data inspection failed: %s", exc)
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"File: {input_csv}")
    print(f"Quality status: {report.status}")
    print(f"Source records: {report.record_count}")
    coverage = (
        f"{report.first_period} through {report.last_period}"
        if report.first_period and report.last_period
        else "none"
    )
    print(f"Source coverage: {coverage}")
    print(f"Chronological source order: {'yes' if report.chronological else 'no'}")
    print(f"Duplicate periods: {_period_list(report.duplicate_periods)}")
    print(f"Missing calendar months: {_period_list(report.missing_periods)}")
    print(f"Selected records: {len(selected)}")

    if report.duplicate_periods:
        print("Descriptive measures: unavailable until duplicate periods are resolved")
    else:
        summary = summarize_records(selected)
        print(f"Minimum: {_number(summary.minimum)}")
        print(f"Maximum: {_number(summary.maximum)}")
        print(f"Latest: {_number(summary.latest)}")
        print(f"Latest change: {_signed_number(summary.latest_change)}")
        print(
            f"Trailing average ({summary.trailing_count} valid observations): "
            f"{_number(summary.trailing_average)}"
        )

    displayed = selected[:limit] if limit is not None else selected
    print(f"Listed records: {len(displayed)}")
    print("series_id,period,value,unit")
    for record in displayed:
        print(
            f"{record['series_id']},{record['period']},{record['value']},"
            f"{record['unit']}"
        )
    return 1 if report.duplicate_periods else 0


def run_demand(
    *,
    start_period: str | None,
    end_period: str | None,
    customer: str | None,
    product_sku: str | None,
    limit: int | None,
) -> int:
    """Calculate, filter, and display the default FRED-driven scenario."""

    try:
        records = load_default_demand()
        selected = filter_demand(
            records,
            start_period=start_period,
            end_period=end_period,
            customer=customer,
            product_sku=product_sku,
        )
    except (OSError, UnicodeError, DemandDataError) as exc:
        logger.error("FRED-driven demand inspection failed: %s", exc)
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    summary = summarize_demand(selected)
    periods = sorted({record["period"] for record in selected})
    coverage = f"{periods[0]} through {periods[-1]}" if periods else "none"
    print("Scenario: FRED-driven fictional internal demand")
    print("Source: fixed FRED PERMIT snapshot, 2000-01 through 2025-12")
    print(f"Demand lag: {DEFAULT_LAG_MONTHS} months")
    print("Cancellations: none")
    print(f"Selected coverage: {coverage}")
    print(f"Selected records: {summary.record_count}")
    print(f"Internal demand units: {summary.demand_units:,}")

    displayed = selected[:limit] if limit is not None else selected
    print(f"Listed records: {len(displayed)}")
    print(",".join(DEMAND_FIELDS))
    for record in displayed:
        print(",".join(str(record[field]) for field in DEMAND_FIELDS))
    return 0


def run_forecast(
    *,
    method: str,
    product_sku: str | None,
    start_period: str,
    end_period: str,
    limit: int | None,
) -> int:
    """Compare approved baselines over the requested evaluation period."""

    try:
        demand_records = load_default_demand()
        records, summaries = compare_baselines(
            demand_records,
            start_period=start_period,
            end_period=end_period,
        )
        selected = filter_forecasts(
            records,
            method=method,
            product_sku=product_sku,
        )
        selected_summary = summarize_forecasts(selected, method)
    except (OSError, UnicodeError, DemandDataError, ForecastError) as exc:
        logger.error("Baseline forecast comparison failed: %s", exc)
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print("Forecast grain: monthly product demand across all customers")
    print(f"Evaluation period: {start_period} through {end_period}")
    print("Error definition: actual - forecast; positive means underforecast")
    print("Baseline comparison:")
    print("method,forecast_count,mae,bias")
    for summary in summaries:
        print(
            f"{summary.method},{summary.forecast_count},"
            f"{_number(summary.mean_absolute_error)},"
            f"{_signed_number(summary.bias)}"
        )
    print(f"Detailed method: {method} ({METHOD_LABELS[method]})")
    print(f"Detailed forecasts: {selected_summary.forecast_count}")
    print(f"Detailed MAE: {_number(selected_summary.mean_absolute_error)}")
    print(f"Detailed bias: {_signed_number(selected_summary.bias)}")

    displayed = selected[:limit] if limit is not None else selected
    print(f"Listed forecasts: {len(displayed)}")
    print("period,product_sku,actual_units,forecast_units,error_units")
    for record in displayed:
        print(
            f"{record['period']},{record['product_sku']},"
            f"{record['actual_units']},{record['forecast_units']:.1f},"
            f"{record['error_units']:+.1f}"
        )
    return 0


def run_fred_forecast(
    *,
    product_sku: str | None,
    horizon_months: int | None,
    limit: int | None,
) -> int:
    """Evaluate the approved rolling-origin FRED-informed forecast."""

    try:
        fred_records = load_fred_snapshot()
        demand_records = load_default_demand()
        records = calculate_driver_forecasts(
            fred_records,
            demand_records,
            default_assumptions(),
        )
        selected = filter_driver_forecasts(
            records,
            product_sku=product_sku,
            horizon_months=horizon_months,
        )
    except (OSError, UnicodeError, DemandDataError, DriverForecastError) as exc:
        logger.error("FRED-informed forecast evaluation failed: %s", exc)
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    known = summarize_driver_status(records, "known")
    forecasted = summarize_driver_status(records, "forecasted")
    print("Forecast grain: monthly product demand across all customers")
    print("Forecast origins: 2019-12 through 2024-12")
    print(f"Demand horizons: 1 through {MAX_FORECAST_HORIZON} months")
    print(f"Unknown-driver method: {DRIVER_METHOD_LABEL}")
    print("Known drivers: demand horizons 1-3 use observed lagged FRED values")
    print("Forecasted drivers: demand horizons 4-12 use the origin FRED value")
    print("Error definition: actual - forecast; positive means underforecast")
    print("Revised-history note: this backtest uses one fixed current FRED snapshot")
    print("driver_status,forecast_count,mae,bias")
    for summary in (known, forecasted):
        print(
            f"{summary.driver_status},{summary.forecast_count},"
            f"{_number(summary.mean_absolute_error)},"
            f"{_signed_number(summary.bias)}"
        )
    print("Horizon performance:")
    print("horizon_months,driver_status,forecast_count,mae,bias")
    for summary in summarize_horizons(records):
        print(
            f"{summary.horizon_months},{summary.driver_status},"
            f"{summary.forecast_count},"
            f"{_number(summary.mean_absolute_error)},"
            f"{_signed_number(summary.bias)}"
        )

    displayed = selected[:limit] if limit is not None else selected
    print(f"Selected forecasts: {len(selected)}")
    print(f"Listed forecasts: {len(displayed)}")
    print(
        "forecast_origin,horizon_months,demand_period,driver_period,"
        "driver_status,product_sku,actual_units,forecast_units,error_units"
    )
    for record in displayed:
        print(
            f"{record['forecast_origin']},{record['horizon_months']},"
            f"{record['demand_period']},{record['driver_period']},"
            f"{record['driver_status']},{record['product_sku']},"
            f"{record['actual_demand_units']},"
            f"{record['forecast_demand_units']},{record['error_units']:+d}"
        )
    return 0


def run_inventory_plan(
    *,
    forecast_origin: str,
    safety_stock_percent: float,
    starting_inventory: dict[str, int],
    product_sku: str | None,
    limit: int | None,
) -> int:
    """Calculate the approved finished-goods inventory plan."""

    try:
        fred_records = load_fred_snapshot()
        assumptions = default_assumptions()
        demand_records = generate_demand(
            fred_records,
            assumptions,
            demand_end_period="2026-01",
        )
        forecasts = calculate_driver_forecasts(
            fred_records,
            demand_records,
            assumptions,
            origin_start=forecast_origin,
            origin_end=forecast_origin,
            max_horizon=13,
        )
        policy = InventoryPolicy(
            starting_inventory=starting_inventory,
            safety_stock_percent=safety_stock_percent,
        )
        records = build_inventory_plan(
            forecasts,
            policy,
            forecast_origin=forecast_origin,
        )
        selected = filter_inventory_plan(records, product_sku=product_sku)
    except (
        OSError,
        UnicodeError,
        DemandDataError,
        DriverForecastError,
        InventoryPlanningError,
    ) as exc:
        logger.error("Inventory planning failed: %s", exc)
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    summary = summarize_inventory_plan(selected)
    print("Plan grain: monthly finished-goods product requirements")
    print(f"Forecast origin: {forecast_origin}")
    print("Planning horizon: 12 months")
    print("Gross requirements: FRED-informed product-demand forecast")
    print(f"Safety stock: {safety_stock_percent:g}% of following-month forecast")
    print("Scheduled receipts: 0 units")
    print("Production timing: available in the planned month")
    print(f"Selected records: {summary.record_count}")
    print(f"Forecast demand units: {summary.forecast_demand_units:,}")
    print(
        "Net production requirement units: "
        f"{summary.net_production_requirement_units:,}"
    )
    print(
        "Final projected inventory units: "
        f"{summary.final_projected_inventory_units:,}"
    )
    displayed = selected[:limit] if limit is not None else selected
    print(f"Listed records: {len(displayed)}")
    print(
        "period,product_sku,forecast_demand,beginning_inventory,"
        "scheduled_receipts,inventory_position,safety_basis_period,"
        "safety_basis_units,safety_target,net_production,projected_ending"
    )
    for record in displayed:
        print(
            f"{record['period']},{record['product_sku']},"
            f"{record['forecast_demand_units']},"
            f"{record['beginning_inventory_units']},"
            f"{record['scheduled_receipts_units']},"
            f"{record['inventory_position_units']},"
            f"{record['safety_stock_basis_period']},"
            f"{record['safety_stock_basis_units']},"
            f"{record['safety_stock_target_units']},"
            f"{record['net_production_requirement_units']},"
            f"{record['projected_ending_inventory_units']}"
        )
    return 0


def run_procurement_plan(
    *,
    forecast_origin: str,
    safety_stock_method: str,
    safety_stock_percent: float,
    service_level: float,
    receipt_treatment: str,
    starting_inventory: dict[str, int],
    component_sku: str | None,
    limit: int | None,
) -> int:
    """Calculate the approved material and supplier-risk plan."""

    try:
        fred_records = load_fred_snapshot()
        assumptions = default_assumptions()
        inputs = prepare_procurement_inputs(
            fred_records,
            assumptions,
            default_inventory_policy(),
            forecast_origin=forecast_origin,
        )
        policy = ProcurementPolicy(
            starting_inventory=starting_inventory,
            safety_stock_method=safety_stock_method,
            percentage=safety_stock_percent,
            service_level=service_level,
            receipt_treatment=receipt_treatment,
        )
        records = build_procurement_plan(
            inputs.material_requirements,
            inputs.supplier_performance,
            inputs.material_error_stats,
            policy,
            forecast_origin=forecast_origin,
        )
        selected = filter_procurement_plan(records, component_sku=component_sku)
        comparisons = compare_safety_stock(
            inputs.material_requirements,
            inputs.material_error_stats,
            inputs.supplier_performance,
            percentage=safety_stock_percent,
            service_level=service_level,
        )
    except (
        OSError,
        UnicodeError,
        DemandDataError,
        DriverForecastError,
        InventoryPlanningError,
        MaterialDataError,
        ProcurementPlanningError,
    ) as exc:
        logger.error("Procurement planning failed: %s", exc)
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    summary = summarize_procurement_plan(selected)
    print("Plan grain: monthly purchased-component requirements")
    print(f"Forecast origin: {forecast_origin}")
    print("BOM scrap: 0%")
    print(f"Material safety-stock method: {safety_stock_method}")
    print(f"Scheduled-receipt treatment: {receipt_treatment}")
    print(f"Selected records: {summary.record_count}")
    print(f"Purchase actions: {summary.purchase_action_count}")
    print(f"Past-due release actions: {summary.past_due_action_count}")
    print(f"Release-now actions: {summary.release_now_action_count}")
    print(f"Receipts with risk adjustment: {summary.receipt_at_risk_count}")
    print("Supplier performance:")
    print("component_sku,delivery_count,on_time_rate,fill_rate,otif_rate")
    for item in inputs.supplier_performance:
        print(
            f"{item.component_sku},{item.delivery_count},"
            f"{item.on_time_rate:.3f},{item.fill_rate:.3f},{item.otif_rate:.3f}"
        )
    print("Safety-stock comparison:")
    print("component_sku,none,percentage,statistical")
    for item in comparisons:
        print(
            f"{item.component_sku},{item.none_target_units},"
            f"{item.percentage_target_units},{item.statistical_target_units}"
        )

    displayed = selected[:limit] if limit is not None else selected
    print(f"Listed records: {len(displayed)}")
    print(
        "period,component_sku,gross_requirement,beginning_inventory,"
        "scheduled_receipt,usable_receipt,safety_target,net_purchase_receipt,"
        "projected_ending,order_release,release_status"
    )
    for record in displayed:
        print(
            f"{record['period']},{record['component_sku']},"
            f"{record['gross_requirement_units']},"
            f"{record['beginning_inventory_units']},"
            f"{record['scheduled_receipt_units']},"
            f"{record['usable_scheduled_receipt_units']},"
            f"{record['safety_stock_target_units']},"
            f"{record['net_purchase_receipt_units']},"
            f"{record['projected_ending_inventory_units']},"
            f"{record['recommended_order_release_period']},"
            f"{record['release_status']}"
        )
    return 0


def run_capacity_plan(
    *,
    forecast_origin: str,
    working_days: int,
    shifts_per_day: int,
    hours_per_shift: float,
    downtime_percent: float,
    setup_hours: float,
    overtime_hours: dict[str, float],
    run_rates: dict[str, float],
    work_center_id: str | None,
    product_sku: str | None,
    limit: int | None,
) -> int:
    """Calculate the approved monthly finite-capacity production plan."""

    try:
        fred_records = load_fred_snapshot()
        assumptions = default_assumptions()
        demand_records = generate_demand(
            fred_records,
            assumptions,
            demand_end_period="2026-01",
        )
        forecasts = calculate_driver_forecasts(
            fred_records,
            demand_records,
            assumptions,
            origin_start=forecast_origin,
            origin_end=forecast_origin,
            max_horizon=13,
        )
        inventory = build_inventory_plan(
            forecasts,
            default_inventory_policy(),
            forecast_origin=forecast_origin,
        )
        policy = CapacityPolicy(
            working_days_per_month=working_days,
            shifts_per_day=shifts_per_day,
            hours_per_shift=hours_per_shift,
            planned_downtime_percent=downtime_percent,
            setup_hours_per_active_product=setup_hours,
            overtime_hours=overtime_hours,
            run_rates=run_rates,
        )
        plan = build_capacity_plan(
            inventory,
            policy,
            forecast_origin=forecast_origin,
        )
        work_centers = filter_work_centers(
            plan.work_centers,
            work_center_id=work_center_id,
        )
        products = filter_capacity_products(
            plan.products,
            product_sku=product_sku,
        )
        if work_center_id is not None:
            products = [
                row
                for row in products
                if row["work_center_id"] == work_center_id
            ]
    except (
        OSError,
        UnicodeError,
        DemandDataError,
        DriverForecastError,
        InventoryPlanningError,
        CapacityPlanningError,
    ) as exc:
        logger.error("Capacity planning failed: %s", exc)
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    summary = summarize_capacity_plan(plan)
    print("Plan grain: monthly product and work-center capacity")
    print(f"Forecast origin: {forecast_origin}")
    print(
        f"Calendar: {working_days} days x {shifts_per_day} shifts x "
        f"{hours_per_shift:g} hours"
    )
    print(f"Planned downtime: {downtime_percent:g}%")
    print(f"Setup: {setup_hours:g} hours per active product")
    print("Allocation: proportional requested runtime; whole units rounded down")
    print(
        "Overloaded work-center months: "
        f"{summary.overloaded_work_center_months}"
    )
    print(f"Ending deferred production units: {summary.ending_deferred_units:,}")
    print(
        "Maximum required utilization: "
        f"{summary.maximum_required_utilization_percent:.1f}%"
    )

    displayed_centers = work_centers[:limit] if limit is not None else work_centers
    print(f"Listed work-center rows: {len(displayed_centers)}")
    print(
        "period,work_center,effective_hours,required_hours,utilization_percent,"
        "capacity_gap,overloaded,planned_units,ending_deferred_units"
    )
    for record in displayed_centers:
        print(
            f"{record['period']},{record['work_center_id']},"
            f"{record['effective_capacity_hours']:.1f},"
            f"{record['required_hours']:.1f},"
            f"{record['required_utilization_percent']:.1f},"
            f"{record['capacity_gap_hours']:+.1f},"
            f"{'yes' if record['overloaded'] else 'no'},"
            f"{record['planned_production_units']},"
            f"{record['ending_deferred_units']}"
        )

    displayed_products = products[:limit] if limit is not None else products
    print(f"Listed product rows: {len(displayed_products)}")
    print(
        "period,work_center,product_sku,base_requirement,beginning_deferred,"
        "total_requested,run_rate,planned_units,ending_deferred"
    )
    for record in displayed_products:
        print(
            f"{record['period']},{record['work_center_id']},"
            f"{record['product_sku']},"
            f"{record['base_production_requirement_units']},"
            f"{record['beginning_deferred_units']},"
            f"{record['total_requested_units']},"
            f"{record['run_rate_units_per_hour']:g},"
            f"{record['planned_production_units']},"
            f"{record['ending_deferred_units']}"
        )
    return 0


def _period_list(periods: Sequence[str]) -> str:
    """Format detected periods without overwhelming the console."""

    if not periods:
        return "none"
    visible = list(periods[:12])
    suffix = f" (+{len(periods) - 12} more)" if len(periods) > 12 else ""
    return ", ".join(visible) + suffix


def _number(value: float | None) -> str:
    """Format an optional observation value."""

    return "not available" if value is None else f"{value:,.1f}"


def _signed_number(value: float | None) -> str:
    """Format an optional difference with an explicit sign."""

    return "not available" if value is None else f"{value:+,.1f}"


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command-line interface."""

    load_dotenv()
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        configure_logging(verbose=args.verbose, log_file=args.log_file)
    except LoggingSetupError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    api_key = os.environ.get("FRED_API_KEY", "").strip()
    logger.debug(
        "Starting command=%s output_dir=%s key_configured=%s.",
        args.command,
        getattr(args, "output_dir", None),
        bool(api_key),
    )

    if args.command == "project-info":
        logger.info("Reporting project setup without calling FRED.")
        print(project_info(api_key_configured=bool(api_key), output_dir=args.output_dir))
        return 0

    if args.command == "inspect":
        logger.info("Inspecting processed observations from %s.", args.input_csv)
        return run_inspect(
            input_csv=args.input_csv,
            start_period=args.start_period,
            end_period=args.end_period,
            limit=args.limit,
        )

    if args.command == "demand":
        logger.info("Inspecting the default FRED-driven demand scenario.")
        return run_demand(
            start_period=args.start_period,
            end_period=args.end_period,
            customer=args.customer,
            product_sku=args.product,
            limit=args.limit,
        )

    if args.command == "forecast":
        logger.info("Comparing internal-demand baseline forecasts.")
        return run_forecast(
            method=args.method,
            product_sku=args.product,
            start_period=args.start_period,
            end_period=args.end_period,
            limit=args.limit,
        )

    if args.command == "fred-forecast":
        logger.info("Evaluating FRED-informed demand forecasts.")
        return run_fred_forecast(
            product_sku=args.product,
            horizon_months=args.horizon,
            limit=args.limit,
        )

    if args.command == "inventory-plan":
        logger.info("Calculating finished-goods inventory requirements.")
        return run_inventory_plan(
            forecast_origin=args.origin,
            safety_stock_percent=args.safety_stock_percent,
            starting_inventory={
                "WIN-2436": args.starting_win_2436,
                "WIN-3648": args.starting_win_3648,
                "DOOR-3680": args.starting_door_3680,
            },
            product_sku=args.product,
            limit=args.limit,
        )

    if args.command == "procurement-plan":
        logger.info("Calculating material and supplier-risk requirements.")
        return run_procurement_plan(
            forecast_origin=args.origin,
            safety_stock_method=args.safety_method,
            safety_stock_percent=args.safety_stock_percent,
            service_level=args.service_level,
            receipt_treatment=args.receipt_treatment,
            starting_inventory={
                component_sku: getattr(
                    args,
                    f"starting_{component_sku.lower().replace('-', '_')}",
                )
                for component_sku in COMPONENTS
            },
            component_sku=args.component,
            limit=args.limit,
        )

    if args.command == "capacity-plan":
        logger.info("Calculating monthly finite-capacity production.")
        return run_capacity_plan(
            forecast_origin=args.origin,
            working_days=args.working_days,
            shifts_per_day=args.shifts_per_day,
            hours_per_shift=args.hours_per_shift,
            downtime_percent=args.downtime_percent,
            setup_hours=args.setup_hours,
            overtime_hours={
                "WINDOW-ASSEMBLY": args.window_overtime,
                "DOOR-ASSEMBLY": args.door_overtime,
            },
            run_rates={
                product_sku: getattr(
                    args,
                    f"rate_{product_sku.lower().replace('-', '_')}",
                )
                for product_sku in PRODUCTS
            },
            work_center_id=args.work_center,
            product_sku=args.product,
            limit=args.limit,
        )

    if not api_key:
        logger.warning("Fetch command stopped because FRED_API_KEY is not configured.")
        print(
            "Error: FRED_API_KEY is not configured. Copy .env.example to .env "
            "and add your own key.",
            file=sys.stderr,
        )
        return 2

    return run_fetch(
        start_date=args.start_date,
        output_dir=args.output_dir,
        api_key=api_key,
    )


if __name__ == "__main__":
    raise SystemExit(main())
