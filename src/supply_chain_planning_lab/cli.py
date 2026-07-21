"""Command-line interface for the data workflow."""

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Sequence

from dotenv import load_dotenv

from .api import FredApiError, fetch_series_observations
from .metadata import project_info
from .output import create_output_paths, write_processed_csv, write_raw_response
from .transform import DataTransformError, transform_observations

SERIES_ID = "PERMIT"
DEFAULT_START_DATE = "2020-01-01"
DEFAULT_OUTPUT_DIR = Path("data")


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
        response = fetch_series_observations(
            api_key=api_key,
            series_id=SERIES_ID,
            observation_start=start_date,
        )
        write_raw_response(paths.raw, response.raw_text)
        records, skipped_missing = transform_observations(
            response.payload, series_id=SERIES_ID
        )
        write_processed_csv(paths.processed, records)
    except (FredApiError, DataTransformError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Fetched FRED series {SERIES_ID}.")
    print(f"Processed {len(records)} valid observations.")
    print(f"Skipped {skipped_missing} missing observations.")
    if records:
        print(f"Period: {records[0]['period']} through {records[-1]['period']}")
    print(f"Raw: {paths.raw}")
    print(f"Processed: {paths.processed}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command-line interface."""

    load_dotenv()
    parser = build_parser()
    args = parser.parse_args(argv)
    api_key = os.environ.get("FRED_API_KEY", "").strip()

    if args.command == "project-info":
        print(project_info(api_key_configured=bool(api_key), output_dir=args.output_dir))
        return 0

    if not api_key:
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
