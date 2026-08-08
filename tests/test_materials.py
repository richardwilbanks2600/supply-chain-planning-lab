import math

from supply_chain_planning_lab.inventory import InventoryPlanRecord
from supply_chain_planning_lab.materials import (
    explode_material_requirements,
    load_supplier_history,
    summarize_supplier_performance,
)


def _production_row(product_sku: str, production_units: int) -> InventoryPlanRecord:
    return InventoryPlanRecord(
        forecast_origin="2024-12",
        horizon_months=1,
        period="2025-01",
        product_sku=product_sku,
        product_name=product_sku,
        forecast_demand_units=production_units,
        beginning_inventory_units=0,
        scheduled_receipts_units=0,
        inventory_position_units=0,
        safety_stock_basis_period="2025-02",
        safety_stock_basis_units=0,
        safety_stock_percent=25.0,
        safety_stock_target_units=0,
        net_production_requirement_units=production_units,
        projected_ending_inventory_units=0,
    )


def test_bom_manual_example_aggregates_shared_window_materials() -> None:
    requirements = explode_material_requirements(
        [
            _production_row("WIN-2436", 100),
            _production_row("WIN-3648", 50),
            _production_row("DOOR-3680", 0),
        ]
    )
    by_component = {row["component_sku"]: row for row in requirements}

    assert by_component["GLASS-SQFT"]["gross_requirement_units"] == 1_200
    assert by_component["VINYL-LNFT"]["gross_requirement_units"] == 1_700
    assert (
        by_component["WINDOW-HARDWARE-KIT"]["gross_requirement_units"]
        == 150
    )
    assert by_component["GLASS-SQFT"]["production_source_units"] == {
        "WIN-2436": 600,
        "WIN-3648": 600,
    }


def test_static_supplier_history_produces_reliability_measures() -> None:
    deliveries = load_supplier_history()
    performance = {
        item.component_sku: item
        for item in summarize_supplier_performance(deliveries)
    }

    assert len(deliveries) == 36
    glass = performance["GLASS-SQFT"]
    assert glass.delivery_count == 6
    assert math.isclose(glass.on_time_rate, 4 / 6)
    assert math.isclose(glass.otif_rate, 3 / 6)
    assert glass.fill_rate < 1
    assert glass.average_actual_lead_months == 2.5
    assert glass.lead_time_standard_deviation > 0
