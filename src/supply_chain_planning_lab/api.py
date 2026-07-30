"""FRED API boundary."""

from dataclasses import dataclass
import logging
from typing import Any

import requests

FRED_OBSERVATIONS_URL = "https://api.stlouisfed.org/fred/series/observations"
DEFAULT_TIMEOUT_SECONDS = 30
logger = logging.getLogger(__name__)


class FredApiError(RuntimeError):
    """Raised when FRED cannot provide a usable response."""


@dataclass(frozen=True)
class FredResponse:
    """The response text and parsed JSON returned by FRED."""

    raw_text: str
    payload: Any


def fetch_series_observations(
    *,
    api_key: str,
    series_id: str,
    observation_start: str,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> FredResponse:
    """Fetch observations for one FRED series."""

    if not api_key.strip():
        raise ValueError("An API key is required.")

    params = {
        "series_id": series_id,
        "observation_start": observation_start,
        "file_type": "json",
        "api_key": api_key,
    }

    try:
        logger.debug(
            "Calling FRED observations endpoint for series=%s start=%s timeout=%s.",
            series_id,
            observation_start,
            timeout,
        )
        response = requests.get(
            FRED_OBSERVATIONS_URL,
            params=params,
            timeout=timeout,
        )
        response.raise_for_status()
    except requests.Timeout as exc:
        logger.warning("FRED request timed out after %s seconds.", timeout)
        raise FredApiError(
            f"FRED did not respond within {timeout} seconds."
        ) from exc
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else "unknown"
        logger.warning("FRED returned HTTP status %s.", status)
        raise FredApiError(
            f"FRED returned HTTP status {status}. Check the key and request values."
        ) from exc
    except requests.RequestException as exc:
        logger.warning("FRED request failed because of a connection problem.")
        raise FredApiError(
            "The FRED request failed because of a network or connection problem."
        ) from exc

    try:
        payload = response.json()
    except requests.JSONDecodeError as exc:
        logger.warning("FRED returned invalid JSON.")
        raise FredApiError("FRED returned a response that was not valid JSON.") from exc

    logger.debug("FRED returned %d response characters.", len(response.text))
    return FredResponse(raw_text=response.text, payload=payload)
