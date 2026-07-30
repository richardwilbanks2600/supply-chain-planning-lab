from typing import Any
from unittest.mock import Mock

import pytest
import requests

from supply_chain_planning_lab import api


class FakeResponse:
    text = '{"observations": [{"date": "2026-06-01", "value": "1367.0"}]}'

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return {
            "observations": [
                {
                    "date": "2026-06-01",
                    "value": "1367.0",
                }
            ]
        }


def test_fetch_series_observations_builds_the_expected_request(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    def fake_get(url: str, *, params: dict[str, str], timeout: int) -> FakeResponse:
        captured.update(url=url, params=params, timeout=timeout)
        return FakeResponse()

    monkeypatch.setattr(api.requests, "get", fake_get)

    response = api.fetch_series_observations(
        api_key="test-key-not-a-secret",
        series_id="PERMIT",
        observation_start="2020-01-01",
    )

    assert captured == {
        "url": api.FRED_OBSERVATIONS_URL,
        "params": {
            "series_id": "PERMIT",
            "observation_start": "2020-01-01",
            "file_type": "json",
            "api_key": "test-key-not-a-secret",
        },
        "timeout": api.DEFAULT_TIMEOUT_SECONDS,
    }
    assert response.raw_text == FakeResponse.text
    assert len(response.payload["observations"]) == 1


def test_fetch_series_observations_explains_timeout(monkeypatch) -> None:
    monkeypatch.setattr(
        api.requests,
        "get",
        Mock(side_effect=requests.Timeout("too slow")),
    )

    with pytest.raises(api.FredApiError, match="within 30 seconds"):
        api.fetch_series_observations(
            api_key="test-key-not-a-secret",
            series_id="PERMIT",
            observation_start="2020-01-01",
        )


def test_fetch_series_observations_explains_http_failure(monkeypatch) -> None:
    response = Mock()
    response.raise_for_status.side_effect = requests.HTTPError(
        response=Mock(status_code=429)
    )
    monkeypatch.setattr(api.requests, "get", Mock(return_value=response))

    with pytest.raises(api.FredApiError, match="HTTP status 429"):
        api.fetch_series_observations(
            api_key="test-key-not-a-secret",
            series_id="PERMIT",
            observation_start="2020-01-01",
        )


def test_fetch_series_observations_explains_connection_failure(monkeypatch) -> None:
    monkeypatch.setattr(
        api.requests,
        "get",
        Mock(side_effect=requests.ConnectionError("offline")),
    )

    with pytest.raises(api.FredApiError, match="network or connection"):
        api.fetch_series_observations(
            api_key="test-key-not-a-secret",
            series_id="PERMIT",
            observation_start="2020-01-01",
        )


def test_fetch_series_observations_rejects_invalid_json(monkeypatch) -> None:
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.side_effect = requests.JSONDecodeError("invalid", "not-json", 0)
    monkeypatch.setattr(api.requests, "get", Mock(return_value=response))

    with pytest.raises(api.FredApiError, match="not valid JSON"):
        api.fetch_series_observations(
            api_key="test-key-not-a-secret",
            series_id="PERMIT",
            observation_start="2020-01-01",
        )
