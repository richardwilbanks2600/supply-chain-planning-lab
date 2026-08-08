"""Shared learner-adjustable assumptions for an integrated planning session."""

from dataclasses import dataclass

from .capacity import CapacityPolicy, default_capacity_policy
from .demand import DemandAssumptions, default_assumptions
from .inventory import InventoryPolicy, default_inventory_policy
from .procurement import ProcurementPolicy, default_procurement_policy


@dataclass(frozen=True)
class PlanningScenario:
    """All approved assumptions that affect the integrated planning workflow."""

    forecast_origin: str
    demand: DemandAssumptions
    finished_goods: InventoryPolicy
    procurement: ProcurementPolicy
    capacity: CapacityPolicy


def default_planning_scenario(*, forecast_origin: str = "2024-12") -> PlanningScenario:
    """Return the approved baseline at a selected historical forecast origin."""

    return PlanningScenario(
        forecast_origin=forecast_origin,
        demand=default_assumptions(),
        finished_goods=default_inventory_policy(),
        procurement=default_procurement_policy(),
        capacity=default_capacity_policy(),
    )
