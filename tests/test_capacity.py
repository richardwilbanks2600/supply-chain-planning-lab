import math

from supply_chain_planning_lab.capacity import (
    CapacityPolicy,
    build_capacity_plan,
    default_capacity_policy,
    summarize_capacity_plan,
)
from supply_chain_planning_lab.demand import (
    PRODUCTS,
    default_assumptions,
    generate_demand,
    load_fred_snapshot,
)
from supply_chain_planning_lab.driver_forecasting import calculate_driver_forecasts
from supply_chain_planning_lab.inventory import (
    InventoryPlanRecord,
    build_inventory_plan,
    default_inventory_policy,
)


def _production_requirement(
    product_sku: str, units: int
) -> InventoryPlanRecord:
    return InventoryPlanRecord(
        forecast_origin="2024-12",
        horizon_months=1,
        period="2025-01",
        product_sku=product_sku,
        product_name=PRODUCTS[product_sku],
        forecast_demand_units=units,
        beginning_inventory_units=0,
        scheduled_receipts_units=0,
        inventory_position_units=0,
        safety_stock_basis_period="2025-02",
        safety_stock_basis_units=0,
        safety_stock_percent=25.0,
        safety_stock_target_units=0,
        net_production_requirement_units=units,
        projected_ending_inventory_units=0,
    )


def test_manual_shared_window_capacity_example() -> None:
    requirements = [
        _production_requirement("WIN-2436", 800),
        _production_requirement("WIN-3648", 600),
        _production_requirement("DOOR-3680", 0),
    ]

    plan = build_capacity_plan(
        requirements,
        default_capacity_policy(),
        forecast_origin="2024-12",
        planning_horizon=1,
    )
    products = {row["product_sku"]: row for row in plan.products}
    window = next(
        row
        for row in plan.work_centers
        if row["work_center_id"] == "WINDOW-ASSEMBLY"
    )

    assert window["effective_capacity_hours"] == 144
    assert window["required_hours"] == 208
    assert window["capacity_gap_hours"] == -64
    assert products["WIN-2436"]["planned_production_units"] == 544
    assert products["WIN-3648"]["planned_production_units"] == 408
    assert products["WIN-2436"]["ending_deferred_units"] == 256
    assert products["WIN-3648"]["ending_deferred_units"] == 192
    assert math.isclose(window["scheduled_hours"], 144)


def test_default_capacity_plan_rolls_deferred_units_without_exceeding_hours() -> None:
    fred = load_fred_snapshot()
    assumptions = default_assumptions()
    demand = generate_demand(
        fred,
        assumptions,
        demand_end_period="2026-01",
    )
    forecasts = calculate_driver_forecasts(
        fred,
        demand,
        assumptions,
        origin_start="2024-12",
        origin_end="2024-12",
        max_horizon=13,
    )
    inventory = build_inventory_plan(
        forecasts,
        default_inventory_policy(),
        forecast_origin="2024-12",
    )

    plan = build_capacity_plan(
        inventory,
        default_capacity_policy(),
        forecast_origin="2024-12",
    )
    summary = summarize_capacity_plan(plan)

    assert len(plan.products) == 36
    assert len(plan.work_centers) == 24
    assert summary.overloaded_work_center_months > 0
    assert all(
        row["scheduled_hours"] <= row["effective_capacity_hours"] + 1e-9
        for row in plan.work_centers
    )
    for product_sku in PRODUCTS:
        rows = [row for row in plan.products if row["product_sku"] == product_sku]
        for previous, current in zip(rows, rows[1:]):
            assert (
                current["beginning_deferred_units"]
                == previous["ending_deferred_units"]
            )


def test_overtime_increases_planned_output() -> None:
    requirements = [
        _production_requirement("WIN-2436", 800),
        _production_requirement("WIN-3648", 600),
        _production_requirement("DOOR-3680", 0),
    ]
    baseline = build_capacity_plan(
        requirements,
        default_capacity_policy(),
        forecast_origin="2024-12",
        planning_horizon=1,
    )
    overtime = build_capacity_plan(
        requirements,
        CapacityPolicy(
            overtime_hours={
                "WINDOW-ASSEMBLY": 40.0,
                "DOOR-ASSEMBLY": 0.0,
            }
        ),
        forecast_origin="2024-12",
        planning_horizon=1,
    )

    assert sum(row["planned_production_units"] for row in overtime.products) > sum(
        row["planned_production_units"] for row in baseline.products
    )
