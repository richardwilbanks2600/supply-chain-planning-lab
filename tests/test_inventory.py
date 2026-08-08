import pytest

from supply_chain_planning_lab.demand import (
    PRODUCTS,
    default_assumptions,
    generate_demand,
    load_fred_snapshot,
)
from supply_chain_planning_lab.driver_forecasting import (
    DriverForecastRecord,
    calculate_driver_forecasts,
)
from supply_chain_planning_lab.inventory import (
    InventoryPlanningError,
    InventoryPolicy,
    build_inventory_plan,
    default_inventory_policy,
    summarize_inventory_plan,
)


def _forecast_record(
    horizon: int, product_sku: str, forecast_units: int
) -> DriverForecastRecord:
    month_index = 2020 * 12 + 3 + horizon - 1
    year, zero_based_month = divmod(month_index, 12)
    return DriverForecastRecord(
        forecast_origin="2020-01",
        horizon_months=horizon,
        demand_period=f"{year:04d}-{zero_based_month + 1:02d}",
        driver_period="2019-10",
        driver_status="known" if horizon <= 3 else "forecasted",
        driver_method="test",
        actual_driver_saar_thousands=0.0,
        driver_value_used_saar_thousands=0.0,
        driver_error_saar_thousands=0.0,
        product_sku=product_sku,
        product_name=PRODUCTS[product_sku],
        actual_demand_units=forecast_units,
        forecast_demand_units=forecast_units,
        error_units=0,
        absolute_error_units=0,
    )


def test_manual_inventory_example_and_roll_forward() -> None:
    records = []
    for horizon in range(1, 14):
        for product_sku in PRODUCTS:
            units = 0
            if product_sku == "WIN-2436" and horizon == 1:
                units = 500
            if product_sku == "WIN-2436" and horizon == 2:
                units = 400
            records.append(_forecast_record(horizon, product_sku, units))
    policy = InventoryPolicy(
        starting_inventory={
            "WIN-2436": 120,
            "WIN-3648": 0,
            "DOOR-3680": 0,
        },
        safety_stock_percent=25.0,
    )

    plan = build_inventory_plan(
        records,
        policy,
        forecast_origin="2020-01",
        planning_horizon=2,
    )

    april_example = plan[0]
    assert april_example["safety_stock_target_units"] == 100
    assert april_example["net_production_requirement_units"] == 480
    assert april_example["projected_ending_inventory_units"] == 100
    assert plan[3]["beginning_inventory_units"] == 100

    surplus_plan = build_inventory_plan(
        records,
        InventoryPolicy(
            starting_inventory={
                "WIN-2436": 700,
                "WIN-3648": 0,
                "DOOR-3680": 0,
            },
            safety_stock_percent=25.0,
        ),
        forecast_origin="2020-01",
        planning_horizon=1,
    )
    assert surplus_plan[0]["net_production_requirement_units"] == 0
    assert surplus_plan[0]["projected_ending_inventory_units"] == 200


def test_default_inventory_plan_has_twelve_months_and_three_products() -> None:
    fred_records = load_fred_snapshot()
    assumptions = default_assumptions()
    demand_records = generate_demand(
        fred_records, assumptions, demand_end_period="2026-01"
    )
    forecasts = calculate_driver_forecasts(
        fred_records,
        demand_records,
        assumptions,
        origin_start="2024-12",
        origin_end="2024-12",
        max_horizon=13,
    )

    plan = build_inventory_plan(
        forecasts,
        default_inventory_policy(),
        forecast_origin="2024-12",
    )
    summary = summarize_inventory_plan(plan)

    assert len(plan) == 36
    assert {record["horizon_months"] for record in plan} == set(range(1, 13))
    assert all(record["scheduled_receipts_units"] == 0 for record in plan)
    assert all(
        record["net_production_requirement_units"] >= 0 for record in plan
    )
    assert summary.record_count == 36
    for product_sku in PRODUCTS:
        product_rows = [
            record for record in plan if record["product_sku"] == product_sku
        ]
        for previous, current in zip(product_rows, product_rows[1:]):
            assert (
                current["beginning_inventory_units"]
                == previous["projected_ending_inventory_units"]
            )


def test_inventory_policy_rejects_missing_or_negative_product_inventory() -> None:
    with pytest.raises(InventoryPlanningError, match="each approved product"):
        InventoryPolicy(starting_inventory={"WIN-2436": 10})

    invalid = dict(default_inventory_policy().starting_inventory)
    invalid["WIN-2436"] = -1
    with pytest.raises(InventoryPlanningError, match="nonnegative whole units"):
        InventoryPolicy(starting_inventory=invalid)
