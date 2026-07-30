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
        args.output_dir,
        bool(api_key),
    )

    if args.command == "project-info":
        logger.info("Reporting project setup without calling FRED.")
        print(project_info(api_key_configured=bool(api_key), output_dir=args.output_dir))
        return 0

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
