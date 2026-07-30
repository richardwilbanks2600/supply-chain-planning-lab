import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from supply_chain_planning_lab.api import FredResponse
from supply_chain_planning_lab.transform import DataTransformError
from supply_chain_planning_lab import workflow

FIXTURE = Path(__file__).parent / "fixtures" / "fred_permit_sample.json"


def test_workflow_uses_controlled_response_and_returns_trusted_records(
    monkeypatch,
) -> None:
    raw_text = FIXTURE.read_text(encoding="utf-8")
    response = FredResponse(raw_text=raw_text, payload=json.loads(raw_text))
    fetch = Mock(return_value=response)
    preserve_raw = Mock()
    monkeypatch.setattr(workflow, "fetch_series_observations", fetch)

    result = workflow.fetch_planning_data(
        api_key="test-key-not-a-secret",
        series_id="PERMIT",
        observation_start="2020-01-01",
        preserve_raw=preserve_raw,
    )

    preserve_raw.assert_called_once_with(response)
    assert len(result.records) == 3
    assert result.skipped_missing == 1
    assert result.raw_text == raw_text


def test_workflow_preserves_bad_outside_data_before_validation(monkeypatch) -> None:
    response = FredResponse(
        raw_text='{"observations": "not-a-list"}',
        payload={"observations": "not-a-list"},
    )
    events: list[str] = []
    monkeypatch.setattr(
        workflow,
        "fetch_series_observations",
        Mock(return_value=response),
    )

    with pytest.raises(DataTransformError, match="validation failed"):
        workflow.fetch_planning_data(
            api_key="test-key-not-a-secret",
            series_id="PERMIT",
            observation_start="2020-01-01",
            preserve_raw=lambda _: events.append("raw-preserved"),
        )

    assert events == ["raw-preserved"]
