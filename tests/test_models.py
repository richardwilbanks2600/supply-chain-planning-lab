import json
from pathlib import Path

import pytest

from supply_chain_planning_lab.models import (
    FredDataValidationError,
    validate_fred_payload,
)

INVALID_FIXTURE = (
    Path(__file__).parent / "fixtures" / "fred_permit_invalid.json"
)


def test_validate_fred_payload_accepts_the_committed_sample() -> None:
    fixture = Path(__file__).parent / "fixtures" / "fred_permit_sample.json"
    payload = json.loads(fixture.read_text(encoding="utf-8"))

    validated = validate_fred_payload(payload)

    assert len(validated.observations) == 4
    assert validated.observations[0].date.isoformat() == "2026-01-01"


def test_validate_fred_payload_identifies_untrusted_fields() -> None:
    payload = json.loads(INVALID_FIXTURE.read_text(encoding="utf-8"))

    with pytest.raises(FredDataValidationError) as error:
        validate_fred_payload(payload)

    message = str(error.value)
    assert "observations.0.date" in message
    assert "observations.1.value" in message
    assert "observations.2.date" in message
