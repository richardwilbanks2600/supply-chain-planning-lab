"""Write generated raw and processed artifacts."""

import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .transform import ProcessedObservation

CSV_FIELDS = ("series_id", "period", "value", "unit")


@dataclass(frozen=True)
class OutputPaths:
    """Paired raw and processed paths for one run."""

    raw: Path
    processed: Path


def create_output_paths(
    output_dir: Path, *, now: datetime | None = None
) -> OutputPaths:
    """Create timestamp-matched output paths without writing files."""

    timestamp_source = now or datetime.now(timezone.utc)
    timestamp = timestamp_source.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    stem = f"fred_permit_{timestamp}"
    return OutputPaths(
        raw=output_dir / "raw" / f"{stem}.json",
        processed=output_dir / "processed" / f"{stem}.csv",
    )


def write_raw_response(path: Path, raw_text: str) -> None:
    """Preserve the response text returned by FRED."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(raw_text, encoding="utf-8")


def write_processed_csv(
    path: Path, records: Iterable[ProcessedObservation]
) -> None:
    """Write normalized observations as CSV."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(records)
