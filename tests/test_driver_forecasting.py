import pytest

from supply_chain_planning_lab.demand import (
    default_assumptions,
    generate_demand,
    load_default_demand,
    load_fred_snapshot,
)
from supply_chain_planning_lab.driver_forecasting import (
    calculate_driver_forecasts,
    filter_driver_forecasts,
    summarize_driver_status,
    summarize_horizons,
)


def _fred(period: str, value: float):
    return {
        "series_id": "PERMIT",
        "period": period,
        "value": value,
        "unit": "thousands_of_units_saar",
    }


def test_known_and_forecasted_driver_manual_example() -> None:
    fred_records = [
        _fred("2019-10", 900.0),
        _fred("2019-11", 950.0),
        _fred("2019-12", 1000.0),
        _fred("2020-01", 1100.0),
    ]
    assumptions = default_assumptions()
    demand_records = generate_demand(
        fred_records, assumptions, demand_end_period="2020-04"
    )

    records = calculate_driver_forecasts(
        fred_records,
        demand_records,
        assumptions,
        origin_start="2019-12",
        origin_end="2019-12",
        max_horizon=4,
    )

    assert len(records) == 12
    assert {record["driver_status"] for record in records[:9]} == {"known"}
    assert all(record["driver_error_saar_thousands"] == 0 for record in records[:9])
    assert any(record["error_units"] != 0 for record in records[:9])
    assert records[0]["actual_demand_units"] == 458
    assert records[0]["forecast_demand_units"] == 450
    assert records[0]["error_units"] == 8
    horizon_four = filter_driver_forecasts(
        records, product_sku="WIN-2436", horizon_months=4
    )
    assert horizon_four == [
        {
            "forecast_origin": "2019-12",
            "horizon_months": 4,
            "demand_period": "2020-04",
            "driver_period": "2020-01",
            "driver_status": "forecasted",
            "driver_method": "previous_month_naive",
            "actual_driver_saar_thousands": 1100.0,
            "driver_value_used_saar_thousands": 1000.0,
            "driver_error_saar_thousands": 100.0,
            "product_sku": "WIN-2436",
            "product_name": "24 x 36 Vinyl Window",
                "actual_demand_units": 549,
                "forecast_demand_units": 500,
                "error_units": 49,
                "absolute_error_units": 49,
        }
    ]


def test_default_backtest_separates_known_driver_from_realized_demand_error() -> None:
    records = calculate_driver_forecasts(
        load_fred_snapshot(),
        load_default_demand(),
        default_assumptions(),
    )

    assert len(records) == 2_196
    known = summarize_driver_status(records, "known")
    forecasted = summarize_driver_status(records, "forecasted")
    assert known.forecast_count == 549
    assert known.mean_absolute_error == pytest.approx(21.8707, abs=0.0001)
    assert known.bias == pytest.approx(-2.7814, abs=0.0001)
    assert forecasted.forecast_count == 1_647
    assert forecasted.mean_absolute_error is not None
    assert forecasted.mean_absolute_error > 0

    horizons = summarize_horizons(records)
    assert len(horizons) == 12
    assert [summary.driver_status for summary in horizons[:3]] == [
        "known",
        "known",
        "known",
    ]
    assert {summary.driver_status for summary in horizons[3:]} == {"forecasted"}
