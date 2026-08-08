"""Coordinate forecast, inventory, material, and supplier planning layers."""

from dataclasses import dataclass

from .demand import DemandAssumptions, generate_demand
from .driver_forecasting import (
    DriverForecastRecord,
    calculate_driver_forecasts,
)
from .inventory import InventoryPlanRecord, InventoryPolicy, build_inventory_plan
from .materials import (
    MaterialRequirementRecord,
    SupplierPerformance,
    explode_material_requirements,
    load_supplier_history,
    summarize_supplier_performance,
)
from .procurement import MaterialErrorStats, calculate_material_error_stats
from .transform import ProcessedObservation


@dataclass(frozen=True)
class ProcurementInputs:
    """Shared upstream records needed by each procurement presentation."""

    origin_forecasts: list[DriverForecastRecord]
    inventory_plan: list[InventoryPlanRecord]
    material_requirements: list[MaterialRequirementRecord]
    material_error_stats: dict[str, MaterialErrorStats]
    supplier_performance: list[SupplierPerformance]


def prepare_procurement_inputs(
    fred_records: list[ProcessedObservation],
    assumptions: DemandAssumptions,
    finished_goods_policy: InventoryPolicy,
    *,
    forecast_origin: str,
) -> ProcurementInputs:
    """Build deterministic Milestone 5-7 inputs without presentation logic."""

    extended_demand = generate_demand(
        fred_records,
        assumptions,
        demand_end_period="2026-02",
    )
    origin_forecasts = calculate_driver_forecasts(
        fred_records,
        extended_demand,
        assumptions,
        origin_start=forecast_origin,
        origin_end=forecast_origin,
        max_horizon=14,
    )
    inventory_plan = build_inventory_plan(
        origin_forecasts,
        finished_goods_policy,
        forecast_origin=forecast_origin,
        planning_horizon=13,
    )
    requirements = explode_material_requirements(inventory_plan)

    historical_demand = generate_demand(fred_records, assumptions)
    historical_forecasts = calculate_driver_forecasts(
        fred_records,
        historical_demand,
        assumptions,
    )
    return ProcurementInputs(
        origin_forecasts=origin_forecasts,
        inventory_plan=inventory_plan,
        material_requirements=requirements,
        material_error_stats=calculate_material_error_stats(
            historical_forecasts
        ),
        supplier_performance=summarize_supplier_performance(
            load_supplier_history()
        ),
    )
