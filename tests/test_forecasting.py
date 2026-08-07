from typing import cast

import pytest

from supply_chain_planning_lab.demand import DemandRecord, load_default_demand
from supply_chain_planning_lab.forecasting import (
    calculate_forecasts,
    compare_baselines,
    summarize_forecasts,
)


def _actual(period: str, units: int) -> DemandRecord:
    return cast(
        DemandRecord,
        {
            "period": period,
            "product_sku": "WIN-2436",
            "demand_units": units,
        },
    )


@pytest.mark.parametrize(
    ("method", "expected_forecast", "expected_error"),
    [
        ("previous_month", 120.0, 10.0),
        ("seasonal_naive", 100.0, 30.0),
        ("trailing_3_average", 105.0, 25.0),
    ],
)
def test_approved_baselines_match_the_manual_example(
    method, expected_forecast, expected_error
) -> None:
    records = [
        _actual("2023-01", 100),
        _actual("2023-10", 90),
        _actual("2023-11", 105),
        _actual("2023-12", 120),
        _actual("2024-01", 130),
    ]

    forecasts = calculate_forecasts(
        records,
        method,
        start_period="2024-01",
        end_period="2024-01",
    )

    assert len(forecasts) == 1
    assert forecasts[0]["forecast_units"] == expected_forecast
    assert forecasts[0]["error_units"] == expected_error
    summary = summarize_forecasts(forecasts, method)
    assert summary.mean_absolute_error == abs(expected_error)
    assert summary.bias == expected_error


def test_default_scenario_has_common_product_month_evaluation_grid() -> None:
    _, summaries = compare_baselines(load_default_demand())

    assert {summary.forecast_count for summary in summaries} == {216}
    assert all(summary.mean_absolute_error is not None for summary in summaries)
    assert all(summary.bias is not None for summary in summaries)
