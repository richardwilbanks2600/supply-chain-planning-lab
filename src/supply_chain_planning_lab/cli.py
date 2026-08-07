"""Command-line interface for the data workflow."""

import argparse
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Sequence

from dotenv import load_dotenv

from .api import FredApiError
from .demand import (
    CUSTOMERS,
    DEMAND_FIELDS,
    PRODUCTS,
    DemandDataError,
    filter_demand,
    load_static_demand,
    summarize_demand,
)
from .inspection import (
    ProcessedDataError,
    filter_records,
    inspect_quality,
    read_processed_csv,
    summarize_records,
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
        help="Inspect the fixed fictional internal-demand scenario.",
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
    """Validate, filter, and display the packaged demand scenario."""

    try:
        records = load_static_demand()
        selected = filter_demand(
            records,
            start_period=start_period,
            end_period=end_period,
            customer=customer,
            product_sku=product_sku,
        )
    except (OSError, UnicodeError, DemandDataError) as exc:
        logger.error("Static-demand inspection failed: %s", exc)
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    summary = summarize_demand(selected)
    periods = sorted({record["period"] for record in selected})
    coverage = f"{periods[0]} through {periods[-1]}" if periods else "none"
    print("Scenario: fixed fictional internal demand")
    print("Generation: none; values are loaded from a version-controlled CSV")
    print(f"Selected coverage: {coverage}")
    print(f"Selected records: {summary.record_count}")
    print(f"Gross ordered units: {summary.gross_order_units:,}")
    print(f"Cancelled units: {summary.cancelled_units:,}")
    print(f"Internal demand units: {summary.demand_units:,}")

    displayed = selected[:limit] if limit is not None else selected
    print(f"Listed records: {len(displayed)}")
    print(",".join(DEMAND_FIELDS))
    for record in displayed:
        print(",".join(str(record[field]) for field in DEMAND_FIELDS))
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
        logger.info("Inspecting the packaged static-demand scenario.")
        return run_demand(
            start_period=args.start_period,
            end_period=args.end_period,
            customer=args.customer,
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
