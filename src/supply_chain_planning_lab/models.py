"""Runtime models for data received from FRED."""

from datetime import date
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator


class FredDataValidationError(ValueError):
    """Raised when FRED data does not match the fields the project relies on."""


class FredObservation(BaseModel):
    """The FRED observation fields used by this project."""

    model_config = ConfigDict(extra="ignore")

    date: date
    value: str

    @field_validator("value")
    @classmethod
    def value_is_numeric_or_missing(cls, value: str) -> str:
        """Accept FRED's missing marker or a value that can become a float."""

        if value == ".":
            return value
        try:
            float(value)
        except ValueError as exc:
            raise ValueError("must be numeric text or the '.' missing marker") from exc
        return value


class FredPayload(BaseModel):
    """Validated subset of a FRED series-observations response."""

    model_config = ConfigDict(extra="ignore")

    observations: list[FredObservation]


def validate_fred_payload(payload: Any) -> FredPayload:
    """Validate outside data and translate Pydantic details into a project error."""

    try:
        return FredPayload.model_validate(payload)
    except ValidationError as exc:
        details = []
        for error in exc.errors(include_url=False)[:3]:
            location = ".".join(str(part) for part in error["loc"])
            details.append(f"{location}: {error['msg']}")
        explanation = "; ".join(details) or "unexpected response structure"
        raise FredDataValidationError(
            f"FRED response validation failed: {explanation}."
        ) from exc
