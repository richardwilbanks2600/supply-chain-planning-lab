from supply_chain_planning_lab.demand import DemandAssumptions, load_fred_snapshot
from supply_chain_planning_lab.integrated_planning import (
    build_integrated_plan,
    records_csv,
)
from supply_chain_planning_lab.scenario import (
    PlanningScenario,
    default_planning_scenario,
)


def test_default_integrated_plan_uses_one_origin_across_every_layer() -> None:
    fred = load_fred_snapshot()
    scenario = default_planning_scenario(forecast_origin="2024-12")

    plan = build_integrated_plan(fred, scenario)

    assert len(plan.inventory_records) == 36
    assert len(plan.procurement_records) == 72
    assert len(plan.capacity_plan.products) == 36
    assert len(plan.capacity_plan.work_centers) == 24
    assert all(
        record["forecast_origin"] == "2024-12"
        for record in (
            *plan.inventory_records,
            *plan.procurement_records,
            *plan.capacity_plan.products,
            *plan.capacity_plan.work_centers,
        )
    )
    assert plan.summary.forecast_demand_units > 0
    assert plan.summary.material_purchase_actions > 0
    assert plan.summary.overloaded_work_center_months > 0


def test_working_demand_assumption_changes_downstream_summary() -> None:
    fred = load_fred_snapshot()
    baseline_scenario = default_planning_scenario(forecast_origin="2024-12")
    baseline = build_integrated_plan(fred, baseline_scenario)
    working = PlanningScenario(
        forecast_origin=baseline_scenario.forecast_origin,
        demand=DemandAssumptions(
            market_share_percent=0.20,
            customer_allocations=baseline_scenario.demand.customer_allocations,
            units_per_home=baseline_scenario.demand.units_per_home,
        ),
        finished_goods=baseline_scenario.finished_goods,
        procurement=baseline_scenario.procurement,
        capacity=baseline_scenario.capacity,
    )

    changed = build_integrated_plan(fred, working)

    assert changed.summary.forecast_demand_units > baseline.summary.forecast_demand_units
    assert (
        changed.summary.net_production_requirement_units
        > baseline.summary.net_production_requirement_units
    )
    assert (
        changed.summary.ending_deferred_production_units
        > baseline.summary.ending_deferred_production_units
    )


def test_in_memory_csv_preserves_nested_lineage() -> None:
    csv_text = records_csv(
        [
            {
                "period": "2025-01",
                "production_source_units": {"WIN-2436": 600},
            }
        ]
    )

    assert csv_text.startswith("period,production_source_units\n")
    assert "2025-01" in csv_text
    assert 'WIN-2436' in csv_text
