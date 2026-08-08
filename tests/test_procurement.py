from supply_chain_planning_lab.demand import (
    default_assumptions,
    generate_demand,
    load_fred_snapshot,
)
from supply_chain_planning_lab.driver_forecasting import calculate_driver_forecasts
from supply_chain_planning_lab.inventory import (
    build_inventory_plan,
    default_inventory_policy,
)
from supply_chain_planning_lab.materials import (
    DEFAULT_MATERIAL_INVENTORY,
    explode_material_requirements,
    load_supplier_history,
    summarize_supplier_performance,
)
from supply_chain_planning_lab.procurement import (
    ProcurementPolicy,
    build_procurement_plan,
    calculate_material_error_stats,
    compare_safety_stock,
    summarize_procurement_plan,
)


def _planning_inputs():
    fred = load_fred_snapshot()
    assumptions = default_assumptions()
    demand = generate_demand(
        fred,
        assumptions,
        demand_end_period="2026-02",
    )
    origin_forecasts = calculate_driver_forecasts(
        fred,
        demand,
        assumptions,
        origin_start="2024-12",
        origin_end="2024-12",
        max_horizon=14,
    )
    inventory = build_inventory_plan(
        origin_forecasts,
        default_inventory_policy(),
        forecast_origin="2024-12",
        planning_horizon=13,
    )
    requirements = explode_material_requirements(inventory)

    historical_demand = generate_demand(fred, assumptions)
    history = calculate_driver_forecasts(fred, historical_demand, assumptions)
    errors = calculate_material_error_stats(history)
    suppliers = summarize_supplier_performance(load_supplier_history())
    return requirements, errors, suppliers


def test_default_procurement_plan_rolls_inventory_and_flags_releases() -> None:
    requirements, errors, suppliers = _planning_inputs()
    policy = ProcurementPolicy(
        starting_inventory=dict(DEFAULT_MATERIAL_INVENTORY),
        safety_stock_method="percentage",
        percentage=25.0,
        receipt_treatment="full",
    )

    plan = build_procurement_plan(
        requirements,
        suppliers,
        errors,
        policy,
        forecast_origin="2024-12",
    )
    summary = summarize_procurement_plan(plan)

    assert len(plan) == 72
    assert summary.record_count == 72
    assert summary.purchase_action_count > 0
    assert summary.past_due_action_count > 0
    assert all(row["net_purchase_receipt_units"] >= 0 for row in plan)
    for component_sku in DEFAULT_MATERIAL_INVENTORY:
        rows = [row for row in plan if row["component_sku"] == component_sku]
        for previous, current in zip(rows, rows[1:]):
            assert (
                current["beginning_inventory_units"]
                == previous["projected_ending_inventory_units"]
            )


def test_statistical_safety_and_risk_adjusted_receipts_use_static_history() -> None:
    requirements, errors, suppliers = _planning_inputs()
    comparisons = {
        item.component_sku: item
        for item in compare_safety_stock(requirements, errors, suppliers)
    }
    glass_comparison = comparisons["GLASS-SQFT"]
    assert glass_comparison.none_target_units == 0
    assert glass_comparison.percentage_target_units > 0
    assert glass_comparison.statistical_target_units > 0

    risk_plan = build_procurement_plan(
        requirements,
        suppliers,
        errors,
        ProcurementPolicy(
            starting_inventory=dict(DEFAULT_MATERIAL_INVENTORY),
            safety_stock_method="statistical",
            receipt_treatment="risk_adjusted",
        ),
        forecast_origin="2024-12",
    )
    first_glass = next(
        row
        for row in risk_plan
        if row["horizon_months"] == 1
        and row["component_sku"] == "GLASS-SQFT"
    )
    assert first_glass["scheduled_receipt_units"] == 4_000
    assert first_glass["usable_scheduled_receipt_units"] == 2_000
    assert first_glass["receipt_at_risk_units"] == 2_000
    assert first_glass["safety_stock_target_units"] == (
        glass_comparison.statistical_target_units
    )
