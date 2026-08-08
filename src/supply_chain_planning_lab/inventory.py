"""Finished-goods inventory roll-forward and net production requirements."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import math
from typing import TypedDict

from .demand import PRODUCTS
from .driver_forecasting import DriverForecastRecord


DEFAULT_SAFETY_STOCK_PERCENT = 25.0
DEFAULT_STARTING_INVENTORY = {
    "WIN-2436": 300,
    "WIN-3648": 200,
    "DOOR-3680": 50,
}
DEFAULT_PLANNING_HORIZON = 12


class InventoryPlanningError(ValueError):
    """Raised when an inventory plan cannot be calculated safely."""


@dataclass(frozen=True)
class InventoryPolicy:
    """Approved starting inventory and safety-stock assumptions."""

    starting_inventory: Mapping[str, int]
    safety_stock_percent: float = DEFAULT_SAFETY_STOCK_PERCENT

    def __post_init__(self) -> None:
        if set(self.starting_inventory) != set(PRODUCTS):
            raise InventoryPlanningError(
                "Starting inventory must contain each approved product exactly once."
            )
        if any(
            isinstance(value, bool) or not isinstance(value, int) or value < 0
            for value in self.starting_inventory.values()
        ):
            raise InventoryPlanningError(
                "Starting inventory values must be nonnegative whole units."
            )
        if (
            not math.isfinite(self.safety_stock_percent)
            or self.safety_stock_percent < 0
            or self.safety_stock_percent > 100
        ):
            raise InventoryPlanningError(
                "Safety-stock percentage must be between 0 and 100."
            )


class InventoryPlanRecord(TypedDict):
    """One product-month inventory calculation with visible components."""

    forecast_origin: str
    horizon_months: int
    period: str
    product_sku: str
    product_name: str
    forecast_demand_units: int
    beginning_inventory_units: int
    scheduled_receipts_units: int
    inventory_position_units: int
    safety_stock_basis_period: str
    safety_stock_basis_units: int
    safety_stock_percent: float
    safety_stock_target_units: int
    net_production_requirement_units: int
    projected_ending_inventory_units: int


@dataclass(frozen=True)
class InventoryPlanSummary:
    """Totals for a selected inventory plan."""

    record_count: int
    forecast_demand_units: int
    net_production_requirement_units: int
    final_projected_inventory_units: int


def default_inventory_policy() -> InventoryPolicy:
    """Return the approved default policy with an independent inventory mapping."""

    return InventoryPolicy(starting_inventory=dict(DEFAULT_STARTING_INVENTORY))


def build_inventory_plan(
    forecast_records: Sequence[DriverForecastRecord],
    policy: InventoryPolicy,
    *,
    forecast_origin: str,
    planning_horizon: int = DEFAULT_PLANNING_HORIZON,
) -> list[InventoryPlanRecord]:
    """Net one origin's demand forecast against finished-goods inventory."""

    if planning_horizon < 1:
        raise InventoryPlanningError("Planning horizon must be at least one month.")

    indexed: dict[tuple[int, str], DriverForecastRecord] = {}
    for record in forecast_records:
        if record["forecast_origin"] != forecast_origin:
            continue
        key = (record["horizon_months"], record["product_sku"])
        if key in indexed:
            raise InventoryPlanningError(
                "Forecast records must be unique by origin, horizon, and product."
            )
        indexed[key] = record

    required_keys = {
        (horizon, product_sku)
        for horizon in range(1, planning_horizon + 2)
        for product_sku in PRODUCTS
    }
    missing = sorted(required_keys - set(indexed))
    if missing:
        horizon, product_sku = missing[0]
        raise InventoryPlanningError(
            f"Forecast horizon {horizon} for {product_sku} is unavailable."
        )

    beginning_inventory = dict(policy.starting_inventory)
    plan: list[InventoryPlanRecord] = []
    for horizon in range(1, planning_horizon + 1):
        for product_sku, product_name in PRODUCTS.items():
            current = indexed[(horizon, product_sku)]
            following = indexed[(horizon + 1, product_sku)]
            forecast_demand = current["forecast_demand_units"]
            safety_basis = following["forecast_demand_units"]
            safety_target = round(
                safety_basis * policy.safety_stock_percent / 100
            )
            scheduled_receipts = 0
            inventory_position = (
                beginning_inventory[product_sku] + scheduled_receipts
            )
            net_production = max(
                0,
                forecast_demand + safety_target - inventory_position,
            )
            projected_ending = (
                inventory_position + net_production - forecast_demand
            )
            plan.append(
                InventoryPlanRecord(
                    forecast_origin=forecast_origin,
                    horizon_months=horizon,
                    period=current["demand_period"],
                    product_sku=product_sku,
                    product_name=product_name,
                    forecast_demand_units=forecast_demand,
                    beginning_inventory_units=beginning_inventory[product_sku],
                    scheduled_receipts_units=scheduled_receipts,
                    inventory_position_units=inventory_position,
                    safety_stock_basis_period=following["demand_period"],
                    safety_stock_basis_units=safety_basis,
                    safety_stock_percent=policy.safety_stock_percent,
                    safety_stock_target_units=safety_target,
                    net_production_requirement_units=net_production,
                    projected_ending_inventory_units=projected_ending,
                )
            )
            beginning_inventory[product_sku] = projected_ending
    return plan


def filter_inventory_plan(
    records: Sequence[InventoryPlanRecord],
    *,
    product_sku: str | None = None,
) -> list[InventoryPlanRecord]:
    """Select inventory rows for one product in stable plan order."""

    if product_sku is not None and product_sku not in PRODUCTS:
        raise InventoryPlanningError(f"Unknown product SKU {product_sku!r}.")
    return [
        record
        for record in records
        if product_sku is None or record["product_sku"] == product_sku
    ]


def summarize_inventory_plan(
    records: Sequence[InventoryPlanRecord],
) -> InventoryPlanSummary:
    """Summarize demand, production, and final projected inventory."""

    final_by_product: dict[str, InventoryPlanRecord] = {}
    for record in records:
        final_by_product[record["product_sku"]] = record
    return InventoryPlanSummary(
        record_count=len(records),
        forecast_demand_units=sum(
            record["forecast_demand_units"] for record in records
        ),
        net_production_requirement_units=sum(
            record["net_production_requirement_units"] for record in records
        ),
        final_projected_inventory_units=sum(
            record["projected_ending_inventory_units"]
            for record in final_by_product.values()
        ),
    )
