"""Transform FRED data into project records."""

from datetime import datetime
from typing import Any, TypedDict

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
    payload: dict[str, Any], *, series_id: str
) -> tuple[list[ProcessedObservation], int]:
    """Normalize valid FRED observations and count missing values."""

    observations = payload.get("observations")
    if not isinstance(observations, list):
        raise DataTransformError("The response does not contain an observations list.")

    processed: list[ProcessedObservation] = []
    skipped_missing = 0

    for index, observation in enumerate(observations):
        if not isinstance(observation, dict):
            raise DataTransformError(f"Observation {index} is not a JSON object.")

        raw_date = observation.get("date")
        raw_value = observation.get("value")

        if raw_value == ".":
            skipped_missing += 1
            continue
        if not isinstance(raw_date, str) or not isinstance(raw_value, str):
            raise DataTransformError(
                f"Observation {index} must contain text date and value fields."
            )

        try:
            period = datetime.strptime(raw_date, "%Y-%m-%d").strftime("%Y-%m")
        except ValueError as exc:
            raise DataTransformError(
                f"Observation {index} has an invalid date: {raw_date!r}."
            ) from exc

        try:
            value = float(raw_value)
        except ValueError as exc:
            raise DataTransformError(
                f"Observation {index} has a nonnumeric value: {raw_value!r}."
            ) from exc

        processed.append(
            {
                "series_id": series_id,
                "period": period,
                "value": value,
                "unit": PROCESSED_UNIT,
            }
        )

    processed.sort(key=lambda record: record["period"])
    return processed, skipped_missing
