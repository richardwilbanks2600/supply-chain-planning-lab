"""Material safety stock, purchasing, and supplier-risk calculations."""

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
import math
from statistics import fmean, stdev
from typing import Literal, TypedDict

from .driver_forecasting import DriverForecastRecord
from .materials import (
    BOM,
    COMPONENTS,
    DEFAULT_MATERIAL_INVENTORY,
    OPEN_ORDER_RECEIPTS,
    MaterialRequirementRecord,
    SupplierPerformance,
)


SafetyStockMethod = Literal["none", "percentage", "statistical"]
ReceiptTreatment = Literal["full", "risk_adjusted"]
ReleaseStatus = Literal["past_due", "release_now", "planned"]
SAFETY_STOCK_METHODS: tuple[SafetyStockMethod, ...] = (
    "none",
    "percentage",
    "statistical",
)
RECEIPT_TREATMENTS: tuple[ReceiptTreatment, ...] = ("full", "risk_adjusted")
SERVICE_LEVEL_Z = {
    90.0: 1.282,
    95.0: 1.645,
    97.5: 1.960,
    99.0: 2.326,
}


class ProcurementPlanningError(ValueError):
    """Raised when a procurement plan cannot be calculated safely."""


@dataclass(frozen=True)
class ProcurementPolicy:
    """Approved raw-material inventory, safety, and receipt assumptions."""

    starting_inventory: Mapping[str, int]
    safety_stock_method: SafetyStockMethod = "percentage"
    percentage: float = 25.0
    service_level: float = 95.0
    receipt_treatment: ReceiptTreatment = "full"

    def __post_init__(self) -> None:
        """Reject incomplete inventory mappings and unsupported policy values."""

        if set(self.starting_inventory) != set(COMPONENTS):
            raise ProcurementPlanningError(
                "Material inventory must contain every component exactly once."
            )
        if any(
            isinstance(value, bool) or not isinstance(value, int) or value < 0
            for value in self.starting_inventory.values()
        ):
            raise ProcurementPlanningError(
                "Material inventory values must be nonnegative whole units."
            )
        if self.safety_stock_method not in SAFETY_STOCK_METHODS:
            raise ProcurementPlanningError("Unknown safety-stock method.")
        if not math.isfinite(self.percentage) or not 0 <= self.percentage <= 100:
            raise ProcurementPlanningError(
                "Safety-stock percentage must be between 0 and 100."
            )
        if self.service_level not in SERVICE_LEVEL_Z:
            raise ProcurementPlanningError("Unsupported service level.")
        if self.receipt_treatment not in RECEIPT_TREATMENTS:
            raise ProcurementPlanningError("Unknown receipt treatment.")


@dataclass(frozen=True)
class MaterialErrorStats:
    """Historical monthly forecast-error variation for one component."""

    component_sku: str
    observation_count: int
    mean_error_units: float
    error_standard_deviation: float


@dataclass(frozen=True)
class SafetyStockComparison:
    """Comparable safety-stock inputs and targets for one component."""

    component_sku: str
    component_name: str
    average_monthly_requirement: float
    forecast_error_standard_deviation: float
    average_actual_lead_months: float
    lead_time_standard_deviation: float
    none_target_units: int
    percentage_target_units: int
    statistical_target_units: int


class ProcurementPlanRecord(TypedDict):
    """One material-month purchasing calculation with full lineage."""

    forecast_origin: str
    horizon_months: int
    period: str
    component_sku: str
    component_name: str
    unit: str
    supplier_id: str
    supplier_name: str
    planned_lead_months: int
    gross_requirement_units: int
    production_source_units: dict[str, int]
    beginning_inventory_units: int
    scheduled_receipt_units: int
    usable_scheduled_receipt_units: int
    receipt_at_risk_units: int
    inventory_position_units: int
    safety_stock_method: SafetyStockMethod
    safety_stock_target_units: int
    net_purchase_receipt_units: int
    projected_ending_inventory_units: int
    recommended_order_release_period: str
    release_status: ReleaseStatus


@dataclass(frozen=True)
class ProcurementPlanSummary:
    """Action counts for a procurement plan without mixing unlike units."""

    record_count: int
    purchase_action_count: int
    past_due_action_count: int
    release_now_action_count: int
    receipt_at_risk_count: int


def default_procurement_policy() -> ProcurementPolicy:
    """Return an independent copy of the approved baseline policy."""

    return ProcurementPolicy(starting_inventory=dict(DEFAULT_MATERIAL_INVENTORY))


def calculate_material_error_stats(
    forecast_records: Sequence[DriverForecastRecord],
) -> dict[str, MaterialErrorStats]:
    """Translate product forecast errors through the BOM and aggregate them."""

    grouped_errors: dict[tuple[str, int, str], float] = defaultdict(float)
    for record in forecast_records:
        if record["driver_status"] != "forecasted":
            continue
        product_sku = record["product_sku"]
        for component_sku, quantity_per in BOM[product_sku]:
            grouped_errors[
                (
                    record["forecast_origin"],
                    record["horizon_months"],
                    component_sku,
                )
            ] += record["error_units"] * quantity_per

    by_component: dict[str, list[float]] = defaultdict(list)
    for (_, _, component_sku), error in grouped_errors.items():
        by_component[component_sku].append(error)

    stats: dict[str, MaterialErrorStats] = {}
    for component_sku in COMPONENTS:
        errors = by_component.get(component_sku, [])
        if len(errors) < 2:
            raise ProcurementPlanningError(
                f"At least two forecast errors are required for {component_sku}."
            )
        stats[component_sku] = MaterialErrorStats(
            component_sku=component_sku,
            observation_count=len(errors),
            mean_error_units=fmean(errors),
            error_standard_deviation=stdev(errors),
        )
    return stats


def compare_safety_stock(
    requirements: Sequence[MaterialRequirementRecord],
    error_stats: Mapping[str, MaterialErrorStats],
    supplier_performance: Sequence[SupplierPerformance],
    *,
    percentage: float = 25.0,
    service_level: float = 95.0,
    displayed_horizon: int = 12,
) -> list[SafetyStockComparison]:
    """Compare no, percentage, and combined statistical safety stock."""

    if service_level not in SERVICE_LEVEL_Z:
        raise ProcurementPlanningError("Unsupported service level.")
    if not math.isfinite(percentage) or not 0 <= percentage <= 100:
        raise ProcurementPlanningError(
            "Safety-stock percentage must be between 0 and 100."
        )
    performance = {item.component_sku: item for item in supplier_performance}
    comparisons = []
    for component_sku, component in COMPONENTS.items():
        selected = [
            row["gross_requirement_units"]
            for row in requirements
            if row["component_sku"] == component_sku
            and row["horizon_months"] <= displayed_horizon
        ]
        if not selected or component_sku not in performance:
            raise ProcurementPlanningError(
                f"Safety-stock inputs are unavailable for {component_sku}."
            )
        average_requirement = fmean(selected)
        stats = error_stats[component_sku]
        supplier = performance[component_sku]
        statistical = _statistical_safety_stock(
            average_monthly_requirement=average_requirement,
            demand_error_standard_deviation=stats.error_standard_deviation,
            average_lead_time=supplier.average_actual_lead_months,
            lead_time_standard_deviation=supplier.lead_time_standard_deviation,
            z_value=SERVICE_LEVEL_Z[service_level],
        )
        comparisons.append(
            SafetyStockComparison(
                component_sku=component_sku,
                component_name=component.name,
                average_monthly_requirement=average_requirement,
                forecast_error_standard_deviation=(
                    stats.error_standard_deviation
                ),
                average_actual_lead_months=(
                    supplier.average_actual_lead_months
                ),
                lead_time_standard_deviation=(
                    supplier.lead_time_standard_deviation
                ),
                none_target_units=0,
                percentage_target_units=round(
                    average_requirement * percentage / 100
                ),
                statistical_target_units=statistical,
            )
        )
    return comparisons


def build_procurement_plan(
    requirements: Sequence[MaterialRequirementRecord],
    supplier_performance: Sequence[SupplierPerformance],
    error_stats: Mapping[str, MaterialErrorStats],
    policy: ProcurementPolicy,
    *,
    forecast_origin: str,
    planning_horizon: int = 12,
) -> list[ProcurementPlanRecord]:
    """Roll material inventory forward and recommend purchase receipts."""

    _parse_period(forecast_origin)
    indexed = {
        (record["horizon_months"], record["component_sku"]): record
        for record in requirements
        if record["forecast_origin"] == forecast_origin
    }
    required = {
        (horizon, component_sku)
        for horizon in range(1, planning_horizon + 2)
        for component_sku in COMPONENTS
    }
    missing = sorted(required - set(indexed))
    if missing:
        horizon, component_sku = missing[0]
        raise ProcurementPlanningError(
            f"Material horizon {horizon} for {component_sku} is unavailable."
        )

    performance = {item.component_sku: item for item in supplier_performance}
    comparisons = {
        item.component_sku: item
        for item in compare_safety_stock(
            requirements,
            error_stats,
            supplier_performance,
            percentage=policy.percentage,
            service_level=policy.service_level,
            displayed_horizon=planning_horizon,
        )
    }
    open_receipts = {
        (horizon, component_sku): quantity
        for horizon, component_sku, quantity in OPEN_ORDER_RECEIPTS
    }
    beginning_inventory = dict(policy.starting_inventory)
    plan: list[ProcurementPlanRecord] = []
    for horizon in range(1, planning_horizon + 1):
        for component_sku in COMPONENTS:
            requirement = indexed[(horizon, component_sku)]
            following = indexed[(horizon + 1, component_sku)]
            supplier = performance[component_sku]
            scheduled_receipt = open_receipts.get((horizon, component_sku), 0)
            usable_receipt = (
                scheduled_receipt
                if policy.receipt_treatment == "full"
                else round(scheduled_receipt * supplier.otif_rate)
            )
            safety_target = _safety_target(
                method=policy.safety_stock_method,
                following_requirement=following["gross_requirement_units"],
                comparison=comparisons[component_sku],
                percentage=policy.percentage,
            )
            inventory_position = beginning_inventory[component_sku] + usable_receipt
            net_purchase = max(
                0,
                requirement["gross_requirement_units"]
                + safety_target
                - inventory_position,
            )
            ending_inventory = (
                inventory_position
                + net_purchase
                - requirement["gross_requirement_units"]
            )
            release_period = _shift_month(
                requirement["period"], -requirement["planned_lead_months"]
            )
            release_status: ReleaseStatus
            if release_period < forecast_origin:
                release_status = "past_due"
            elif release_period == forecast_origin:
                release_status = "release_now"
            else:
                release_status = "planned"
            plan.append(
                ProcurementPlanRecord(
                    forecast_origin=forecast_origin,
                    horizon_months=horizon,
                    period=requirement["period"],
                    component_sku=component_sku,
                    component_name=requirement["component_name"],
                    unit=requirement["unit"],
                    supplier_id=requirement["supplier_id"],
                    supplier_name=requirement["supplier_name"],
                    planned_lead_months=requirement["planned_lead_months"],
                    gross_requirement_units=requirement[
                        "gross_requirement_units"
                    ],
                    production_source_units=requirement[
                        "production_source_units"
                    ],
                    beginning_inventory_units=beginning_inventory[component_sku],
                    scheduled_receipt_units=scheduled_receipt,
                    usable_scheduled_receipt_units=usable_receipt,
                    receipt_at_risk_units=scheduled_receipt - usable_receipt,
                    inventory_position_units=inventory_position,
                    safety_stock_method=policy.safety_stock_method,
                    safety_stock_target_units=safety_target,
                    net_purchase_receipt_units=net_purchase,
                    projected_ending_inventory_units=ending_inventory,
                    recommended_order_release_period=release_period,
                    release_status=release_status,
                )
            )
            beginning_inventory[component_sku] = ending_inventory
    return plan


def filter_procurement_plan(
    records: Sequence[ProcurementPlanRecord],
    *,
    component_sku: str | None = None,
) -> list[ProcurementPlanRecord]:
    """Select procurement records for one component."""

    if component_sku is not None and component_sku not in COMPONENTS:
        raise ProcurementPlanningError(f"Unknown component SKU {component_sku!r}.")
    return [
        record
        for record in records
        if component_sku is None or record["component_sku"] == component_sku
    ]


def summarize_procurement_plan(
    records: Sequence[ProcurementPlanRecord],
) -> ProcurementPlanSummary:
    """Count purchase and timing actions without adding unlike material units."""

    purchasing = [row for row in records if row["net_purchase_receipt_units"] > 0]
    return ProcurementPlanSummary(
        record_count=len(records),
        purchase_action_count=len(purchasing),
        past_due_action_count=sum(
            row["release_status"] == "past_due" for row in purchasing
        ),
        release_now_action_count=sum(
            row["release_status"] == "release_now" for row in purchasing
        ),
        receipt_at_risk_count=sum(
            row["receipt_at_risk_units"] > 0 for row in records
        ),
    )


def _safety_target(
    *,
    method: SafetyStockMethod,
    following_requirement: int,
    comparison: SafetyStockComparison,
    percentage: float,
) -> int:
    """Select the whole-unit safety target for the configured method."""

    if method == "none":
        return 0
    if method == "percentage":
        return round(following_requirement * percentage / 100)
    return comparison.statistical_target_units


def _statistical_safety_stock(
    *,
    average_monthly_requirement: float,
    demand_error_standard_deviation: float,
    average_lead_time: float,
    lead_time_standard_deviation: float,
    z_value: float,
) -> int:
    """Estimate whole-unit safety stock from demand and lead-time variation."""

    variance = (
        average_lead_time * demand_error_standard_deviation**2
        + average_monthly_requirement**2 * lead_time_standard_deviation**2
    )
    return round(z_value * math.sqrt(variance))


def _parse_period(value: str) -> date:
    """Parse a canonical monthly period used by procurement calculations."""

    try:
        parsed = date.fromisoformat(f"{value}-01")
    except ValueError as exc:
        raise ProcurementPlanningError(
            f"Invalid period {value!r}; expected YYYY-MM."
        ) from exc
    if parsed.strftime("%Y-%m") != value:
        raise ProcurementPlanningError(
            f"Invalid period {value!r}; expected YYYY-MM."
        )
    return parsed


def _shift_month(period: str, months: int) -> str:
    """Shift a canonical monthly period by a signed number of months."""

    parsed = _parse_period(period)
    month_index = parsed.year * 12 + parsed.month - 1 + months
    year, zero_based_month = divmod(month_index, 12)
    return f"{year:04d}-{zero_based_month + 1:02d}"
