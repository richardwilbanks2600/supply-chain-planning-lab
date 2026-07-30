import json
from pathlib import Path

import pytest

from supply_chain_planning_lab.transform import (
    DataTransformError,
    transform_observations,
)

FIXTURE = Path(__file__).parent / "fixtures" / "fred_permit_sample.json"


def test_transform_observations_normalizes_records_and_skips_missing_values() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))

    records, skipped_missing = transform_observations(payload, series_id="PERMIT")

    assert skipped_missing == 1
    assert records == [
        {
            "series_id": "PERMIT",
            "period": "2026-01",
            "value": 1393.0,
            "unit": "thousands_of_units_saar",
        },
        {
            "series_id": "PERMIT",
            "period": "2026-03",
            "value": 1363.0,
            "unit": "thousands_of_units_saar",
        },
        {
            "series_id": "PERMIT",
            "period": "2026-04",
            "value": 1423.0,
            "unit": "thousands_of_units_saar",
        },
    ]


def test_transform_observations_rejects_invalid_shape() -> None:
    with pytest.raises(DataTransformError, match="validation failed"):
        transform_observations({}, series_id="PERMIT")
