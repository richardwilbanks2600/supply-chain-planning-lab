"""Validate, filter, and describe processed observation files."""

from collections import Counter
from collections.abc import Sequence
import csv
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from statistics import fmean
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from .transform import ProcessedObservation

EXPECTED_FIELDS = ("series_id", "period", "value", "unit")
TRAILING_WINDOW = 12


class ProcessedDataError(ValueError):
    """Raised when a processed CSV cannot be interpreted safely."""


class ProcessedObservationModel(BaseModel):
    """Runtime-validated representation of one processed PERMIT row."""

    model_config = ConfigDict(extra="forbid")

    series_id: Literal["PERMIT"]
    period: str
    value: float = Field(allow_inf_nan=False)
    unit: Literal["thousands_of_units_saar"]

    @field_validator("period")
    @classmethod
    def period_is_canonical_month(cls, value: str) -> str:
        """Require a zero-padded calendar month in YYYY-MM form."""

        try:
            parsed = date.fromisoformat(f"{value}-01")
        except ValueError as exc:
            raise ValueError("must be a calendar month in YYYY-MM format") from exc
        if parsed.strftime("%Y-%m") != value:
            raise ValueError("must be a calendar month in YYYY-MM format")
        return value

    def as_record(self) -> ProcessedObservation:
        """Convert the validated model to the project's CSV record shape."""

        return {
            "series_id": self.series_id,
            "period": self.period,
            "value": self.value,
            "unit": self.unit,
        }


@dataclass(frozen=True)
class DataQualityReport:
    """Structural observations about a processed dataset."""

    record_count: int
    first_period: str | None
    last_period: str | None
    chronological: bool
    duplicate_periods: tuple[str, ...]
    missing_periods: tuple[str, ...]

    @property
    def status(self) -> str:
        """Return a concise severity label for command output."""

        if self.duplicate_periods:
            return "FAIL"
        if not self.chronological or self.missing_periods:
            return "WARNING"
        return "PASS"


@dataclass(frozen=True)
class DescriptiveSummary:
    """Transparent descriptive measures for valid, unique observations."""

    record_count: int
    minimum: float | None
    maximum: float | None
    latest: float | None
    latest_change: float | None
    trailing_average: float | None
    trailing_count: int


def read_processed_csv(path: Path) -> list[ProcessedObservation]:
    """Read and runtime-validate a processed PERMIT CSV file."""

    with path.open(encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        actual_fields = tuple(reader.fieldnames or ())
        if actual_fields != EXPECTED_FIELDS:
            expected = ",".join(EXPECTED_FIELDS)
            received = ",".join(actual_fields) or "no header"
            raise ProcessedDataError(
                f"Expected CSV header {expected}; received {received}."
            )

        records: list[ProcessedObservation] = []
        for line_number, row in enumerate(reader, start=2):
            try:
                model = ProcessedObservationModel.model_validate(row)
            except ValidationError as exc:
                first_error = exc.errors(include_url=False)[0]
                field = ".".join(str(part) for part in first_error["loc"])
                raise ProcessedDataError(
                    f"CSV line {line_number} has invalid {field}: "
                    f"{first_error['msg']}."
                ) from exc
            records.append(model.as_record())
    return records


def inspect_quality(records: Sequence[ProcessedObservation]) -> DataQualityReport:
    """Detect duplicates, gaps, and unexpected source ordering."""

    periods = [record["period"] for record in records]
    sorted_periods = sorted(periods)
    counts = Counter(periods)
    duplicates = tuple(sorted(period for period, count in counts.items() if count > 1))
    unique_periods = sorted(counts)
    missing = _missing_months(unique_periods)
    return DataQualityReport(
        record_count=len(records),
        first_period=unique_periods[0] if unique_periods else None,
        last_period=unique_periods[-1] if unique_periods else None,
        chronological=periods == sorted_periods,
        duplicate_periods=duplicates,
        missing_periods=missing,
    )


def filter_records(
    records: Sequence[ProcessedObservation],
    *,
    start_period: str | None = None,
    end_period: str | None = None,
) -> list[ProcessedObservation]:
    """Select an inclusive month range and return it chronologically."""

    if start_period is not None:
        _parse_period(start_period)
    if end_period is not None:
        _parse_period(end_period)
    if start_period and end_period and start_period > end_period:
        raise ProcessedDataError("Start period must not be later than end period.")

    selected = [
        record
        for record in records
        if (start_period is None or record["period"] >= start_period)
        and (end_period is None or record["period"] <= end_period)
    ]
    return sorted(selected, key=lambda record: record["period"])


def summarize_records(
    records: Sequence[ProcessedObservation],
    *,
    trailing_window: int = TRAILING_WINDOW,
) -> DescriptiveSummary:
    """Calculate approved descriptive measures without forecasting."""

    if trailing_window < 1:
        raise ValueError("trailing_window must be at least 1")
    ordered = sorted(records, key=lambda record: record["period"])
    if not ordered:
        return DescriptiveSummary(0, None, None, None, None, None, 0)

    values = [record["value"] for record in ordered]
    trailing_values = values[-trailing_window:]
    latest_change = values[-1] - values[-2] if len(values) >= 2 else None
    return DescriptiveSummary(
        record_count=len(values),
        minimum=min(values),
        maximum=max(values),
        latest=values[-1],
        latest_change=latest_change,
        trailing_average=fmean(trailing_values),
        trailing_count=len(trailing_values),
    )


def _missing_months(sorted_unique_periods: Sequence[str]) -> tuple[str, ...]:
    """Return calendar months absent between the first and last records."""

    if len(sorted_unique_periods) < 2:
        return ()
    present = set(sorted_unique_periods)
    current = _next_month(_parse_period(sorted_unique_periods[0]))
    last = _parse_period(sorted_unique_periods[-1])
    missing: list[str] = []
    while current < last:
        period = current.strftime("%Y-%m")
        if period not in present:
            missing.append(period)
        current = _next_month(current)
    return tuple(missing)


def _parse_period(value: str) -> date:
    """Parse one canonical YYYY-MM period."""

    try:
        parsed = date.fromisoformat(f"{value}-01")
    except ValueError as exc:
        raise ProcessedDataError(
            f"Invalid period {value!r}; expected YYYY-MM."
        ) from exc
    if parsed.strftime("%Y-%m") != value:
        raise ProcessedDataError(f"Invalid period {value!r}; expected YYYY-MM.")
    return parsed


def _next_month(value: date) -> date:
    """Return the first day of the following calendar month."""

    if value.month == 12:
        return date(value.year + 1, 1, 1)
    return date(value.year, value.month + 1, 1)
