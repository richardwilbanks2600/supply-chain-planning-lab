"""Transform FRED data into project records."""

from typing import Any, TypedDict

from .models import FredDataValidationError, FredPayload, validate_fred_payload

PROCESSED_UNIT = "thousands_of_units_saar"


class DataTransformError(ValueError):
    """Raised when a response cannot be transformed safely."""


class ProcessedObservation(TypedDict):
    """One normalized monthly observation."""

    series_id: str
    period: str
    value: float
    unit: str


def transform_observations(
    payload: FredPayload | dict[str, Any], *, series_id: str
) -> tuple[list[ProcessedObservation], int]:
    """Validate and normalize FRED observations, counting missing values."""

    try:
        validated = (
            payload
            if isinstance(payload, FredPayload)
            else validate_fred_payload(payload)
        )
    except FredDataValidationError as exc:
        raise DataTransformError(str(exc)) from exc
    processed: list[ProcessedObservation] = []
    skipped_missing = 0

    for observation in validated.observations:
        raw_value = observation.value
        if raw_value == ".":
            skipped_missing += 1
            continue

        processed.append(
            {
                "series_id": series_id,
                "period": observation.date.strftime("%Y-%m"),
                "value": float(raw_value),
                "unit": PROCESSED_UNIT,
            }
        )

    processed.sort(key=lambda record: record["period"])
    return processed, skipped_missing
