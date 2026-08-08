"""Build and summarize one consistent forecast-to-capacity planning scenario."""

from collections.abc import Mapping, Sequence
import csv
from dataclasses import dataclass
from io import StringIO
import json
from typing import Any

from .capacity import CapacityPlan, build_capacity_plan, summarize_capacity_plan
from .demand import DemandRecord, generate_demand
from .inventory import InventoryPlanRecord, summarize_inventory_plan
from .planning_workflow import ProcurementInputs, prepare_procurement_inputs
from .procurement import (
    ProcurementPlanRecord,
    build_procurement_plan,
    summarize_procurement_plan,
)
from .scenario import PlanningScenario
from .transform import ProcessedObservation


@dataclass(frozen=True)
class IntegratedPlanSummary:
    """Comparable measures for baseline and working scenarios."""

    forecast_demand_units: int
    net_production_requirement_units: int
    material_purchase_actions: int
    past_due_release_actions: int
    risk_adjusted_receipts: int
    overloaded_work_center_months: int
    ending_deferred_production_units: int


@dataclass(frozen=True)
class IntegratedPlan:
    """All shared records rendered by the learner dashboard."""

    scenario: PlanningScenario
    demand_records: list[DemandRecord]
    procurement_inputs: ProcurementInputs
    inventory_records: list[InventoryPlanRecord]
    procurement_records: list[ProcurementPlanRecord]
    capacity_plan: CapacityPlan
    summary: IntegratedPlanSummary


def build_integrated_plan(
    fred_records: list[ProcessedObservation],
    scenario: PlanningScenario,
) -> IntegratedPlan:
    """Run every approved planning layer from one shared scenario."""

    demand_records = generate_demand(fred_records, scenario.demand)
    inputs = prepare_procurement_inputs(
        fred_records,
        scenario.demand,
        scenario.finished_goods,
        forecast_origin=scenario.forecast_origin,
    )
    inventory_records = [
        record
        for record in inputs.inventory_plan
        if record["horizon_months"] <= 12
    ]
    procurement_records = build_procurement_plan(
        inputs.material_requirements,
        inputs.supplier_performance,
        inputs.material_error_stats,
        scenario.procurement,
        forecast_origin=scenario.forecast_origin,
    )
    capacity_plan = build_capacity_plan(
        inventory_records,
        scenario.capacity,
        forecast_origin=scenario.forecast_origin,
    )
    inventory_summary = summarize_inventory_plan(inventory_records)
    procurement_summary = summarize_procurement_plan(procurement_records)
    capacity_summary = summarize_capacity_plan(capacity_plan)
    summary = IntegratedPlanSummary(
        forecast_demand_units=inventory_summary.forecast_demand_units,
        net_production_requirement_units=(
            inventory_summary.net_production_requirement_units
        ),
        material_purchase_actions=procurement_summary.purchase_action_count,
        past_due_release_actions=procurement_summary.past_due_action_count,
        risk_adjusted_receipts=procurement_summary.receipt_at_risk_count,
        overloaded_work_center_months=(
            capacity_summary.overloaded_work_center_months
        ),
        ending_deferred_production_units=capacity_summary.ending_deferred_units,
    )
    return IntegratedPlan(
        scenario=scenario,
        demand_records=demand_records,
        procurement_inputs=inputs,
        inventory_records=inventory_records,
        procurement_records=procurement_records,
        capacity_plan=capacity_plan,
        summary=summary,
    )


def records_csv(records: Sequence[Mapping[str, Any]]) -> str:
    """Serialize current in-memory planning records without external writes."""

    if not records:
        return ""
    output = StringIO(newline="")
    fields = tuple(records[0])
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for record in records:
        writer.writerow(
            {
                field: (
                    json.dumps(value, sort_keys=True)
                    if isinstance(value, (dict, list, tuple))
                    else value
                )
                for field, value in record.items()
            }
        )
    return output.getvalue()
