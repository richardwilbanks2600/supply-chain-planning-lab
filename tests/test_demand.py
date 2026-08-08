import pytest

from supply_chain_planning_lab.demand import (
    DemandAssumptions,
    DemandDataError,
    default_assumptions,
    filter_demand,
    generate_demand,
    load_fred_snapshot,
    load_realization_factors,
    monthly_demand,
    monthly_demand_comparison,
    summarize_demand,
)


def _fred_record(period: str = "2000-01", value: float = 1500.0):
    return {
        "series_id": "PERMIT",
        "period": period,
        "value": value,
        "unit": "thousands_of_units_saar",
    }


def test_packaged_fred_snapshot_is_complete_and_fixed() -> None:
    records = load_fred_snapshot()

    assert len(records) == 312
    assert records[0]["period"] == "2000-01"
    assert records[-1]["period"] == "2025-12"
    assert records[0]["value"] == 1727.0
    assert records[-1]["value"] == 1482.0


def test_default_scenario_covers_april_2000_through_december_2025() -> None:
    records = generate_demand(load_fred_snapshot(), default_assumptions())

    assert len(records) == 2_781
    assert records[0]["period"] == "2000-04"
    assert records[-1]["period"] == "2025-12"


def test_packaged_realization_factors_are_complete_static_and_bounded() -> None:
    factors = load_realization_factors()

    assert len(factors) == 933
    assert len({(row["period"], row["product_sku"]) for row in factors}) == 933
    assert factors[0]["period"] == "2000-04"
    assert factors[-1]["period"] == "2026-02"
    values = [row["realization_factor"] for row in factors]
    assert min(values) == 0.75
    assert max(values) == 1.25
    assert sum(0.85 <= value <= 1.15 for value in values) / len(values) > 0.95
    assert {row["variation_type"] for row in factors} == {"typical", "unusual"}


def test_demand_calculation_preserves_source_lineage_and_product_totals() -> None:
    records = generate_demand(
        [_fred_record()],
        default_assumptions(),
        demand_end_period="2000-04",
    )

    assert len(records) == 9
    assert {record["period"] for record in records} == {"2000-04"}
    assert {record["fred_period"] for record in records} == {"2000-01"}
    assert {record["monthly_housing_pace"] for record in records} == {125_000.0}
    summary = summarize_demand(records)
    assert summary.fred_expected_demand_units == 1_375
    assert summary.demand_units == 1_457
    assert sum(
        record["demand_units"]
        for record in records
        if record["product_sku"] == "WIN-2436"
    ) == 794
    assert {
        record["realization_factor"]
        for record in records
        if record["product_sku"] == "WIN-2436"
    } == {1.0582}


def test_slider_assumptions_change_demand_deterministically() -> None:
    baseline = generate_demand(
        [_fred_record()], default_assumptions(), demand_end_period="2000-04"
    )
    doubled_share = DemandAssumptions(
        market_share_percent=0.20,
        customer_allocations={
            "Building Houses Company": 0.50,
            "Building Supply Company": 0.30,
            "Building Remodeler": 0.20,
        },
        units_per_home={
            "WIN-2436": 6.0,
            "WIN-3648": 4.0,
            "DOOR-3680": 1.0,
        },
    )
    changed = generate_demand(
        [_fred_record()], doubled_share, demand_end_period="2000-04"
    )

    assert abs(
        summarize_demand(changed).demand_units
        - summarize_demand(baseline).demand_units * 2
    ) <= 3


def test_demand_filters_and_monthly_totals_are_additive() -> None:
    records = generate_demand(
        [_fred_record("2000-01"), _fred_record("2000-02", 1200.0)],
        default_assumptions(),
        demand_end_period="2000-05",
    )
    selected = filter_demand(
        records,
        customer="Building Houses Company",
        product_sku="WIN-2436",
    )

    assert [record["period"] for record in selected] == ["2000-04", "2000-05"]
    assert monthly_demand(selected) == [
        {"period": "2000-04", "demand_units": 397},
        {"period": "2000-05", "demand_units": 336},
    ]
    assert monthly_demand_comparison(selected) == [
        {
            "period": "2000-04",
            "fred_expected_demand_units": 375,
            "realized_demand_units": 397,
        },
        {
            "period": "2000-05",
            "fred_expected_demand_units": 300,
            "realized_demand_units": 336,
        },
    ]


def test_assumptions_require_customer_allocations_to_total_one() -> None:
    with pytest.raises(DemandDataError, match="total 100 percent"):
        DemandAssumptions(
            market_share_percent=0.10,
            customer_allocations={
                "Building Houses Company": 0.50,
                "Building Supply Company": 0.30,
                "Building Remodeler": 0.30,
            },
            units_per_home={
                "WIN-2436": 6.0,
                "WIN-3648": 4.0,
                "DOOR-3680": 1.0,
            },
        )
