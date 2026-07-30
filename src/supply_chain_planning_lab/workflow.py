"""Shared FRED retrieval and transformation workflow."""

from collections.abc import Callable
from dataclasses import dataclass
import logging

from .api import FredResponse, fetch_series_observations
from .transform import ProcessedObservation, transform_observations

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PlanningResult:
    """Trusted observations plus the outside evidence used to create them."""

    raw_text: str
    records: tuple[ProcessedObservation, ...]
    skipped_missing: int


def fetch_planning_data(
    *,
    api_key: str,
    series_id: str,
    observation_start: str,
    preserve_raw: Callable[[FredResponse], None] | None = None,
) -> PlanningResult:
    """Fetch, optionally preserve, validate, and transform one FRED response."""

    logger.info(
        "Requesting FRED series %s starting %s.", series_id, observation_start
    )
    response = fetch_series_observations(
        api_key=api_key,
        series_id=series_id,
        observation_start=observation_start,
    )

    if preserve_raw is not None:
        preserve_raw(response)
        logger.info("Preserved the raw FRED response before validation.")

    records, skipped_missing = transform_observations(
        response.payload, series_id=series_id
    )
    logger.info(
        "Validated and transformed %d observations; skipped %d missing values.",
        len(records),
        skipped_missing,
    )
    return PlanningResult(
        raw_text=response.raw_text,
        records=tuple(records),
        skipped_missing=skipped_missing,
    )
