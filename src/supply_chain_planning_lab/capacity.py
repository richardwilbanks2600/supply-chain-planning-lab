"""Monthly work-center capacity allocation and deferred production."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import math
from typing import TypedDict

from .demand import PRODUCTS
from .inventory import InventoryPlanRecord


WORK_CENTERS = {
    "WINDOW-ASSEMBLY": "Window Assembly",
    "DOOR-ASSEMBLY": "Door Assembly",
}
PRODUCT_WORK_CENTERS = {
    "WIN-2436": "WINDOW-ASSEMBLY",
    "WIN-3648": "WINDOW-ASSEMBLY",
    "DOOR-3680": "DOOR-ASSEMBLY",
}
DEFAULT_RUN_RATES = {
    "WIN-2436": 8.0,
    "WIN-3648": 6.0,
    "DOOR-3680": 1.0,
}
DEFAULT_WORKING_DAYS = 20
DEFAULT_SHIFTS_PER_DAY = 1
DEFAULT_HOURS_PER_SHIFT = 8.0
DEFAULT_DOWNTIME_PERCENT = 10.0
DEFAULT_SETUP_HOURS = 4.0
DEFAULT_OVERTIME_HOURS = {
    "WINDOW-ASSEMBLY": 0.0,
    "DOOR-ASSEMBLY": 0.0,
}
DEFAULT_CAPACITY_HORIZON = 12


class CapacityPlanningError(ValueError):
    """Raised when a capacity plan cannot be calculated safely."""


@dataclass(frozen=True)
class CapacityPolicy:
    """Approved calendar, availability, setup, and run-rate assumptions."""

    working_days_per_month: int = DEFAULT_WORKING_DAYS
    shifts_per_day: int = DEFAULT_SHIFTS_PER_DAY
    hours_per_shift: float = DEFAULT_HOURS_PER_SHIFT
    planned_downtime_percent: float = DEFAULT_DOWNTIME_PERCENT
    setup_hours_per_active_product: float = DEFAULT_SETUP_HOURS
    overtime_hours: Mapping[str, float] | None = None
    run_rates: Mapping[str, float] | None = None

    def __post_init__(self) -> None:
        overtime = (
            dict(DEFAULT_OVERTIME_HOURS)
            if self.overtime_hours is None
            else self.overtime_hours
        )
        rates = dict(DEFAULT_RUN_RATES) if self.run_rates is None else self.run_rates
        object.__setattr__(self, "overtime_hours", overtime)
        object.__setattr__(self, "run_rates", rates)
        if (
            isinstance(self.working_days_per_month, bool)
            or not isinstance(self.working_days_per_month, int)
            or self.working_days_per_month < 1
            or self.working_days_per_month > 31
        ):
            raise CapacityPlanningError("Working days must be an integer from 1 to 31.")
        if (
            isinstance(self.shifts_per_day, bool)
            or not isinstance(self.shifts_per_day, int)
            or self.shifts_per_day < 1
            or self.shifts_per_day > 3
        ):
            raise CapacityPlanningError("Shifts per day must be an integer from 1 to 3.")
        if not math.isfinite(self.hours_per_shift) or self.hours_per_shift <= 0:
            raise CapacityPlanningError("Hours per shift must be positive and finite.")
        if (
            not math.isfinite(self.planned_downtime_percent)
            or not 0 <= self.planned_downtime_percent < 100
        ):
            raise CapacityPlanningError("Downtime must be at least 0 and below 100%.")
        if (
            not math.isfinite(self.setup_hours_per_active_product)
            or self.setup_hours_per_active_product < 0
        ):
            raise CapacityPlanningError("Setup hours must be finite and nonnegative.")
        if set(overtime) != set(WORK_CENTERS) or any(
            not math.isfinite(value) or value < 0 for value in overtime.values()
        ):
            raise CapacityPlanningError(
                "Overtime must contain a nonnegative value for every work center."
            )
        if set(rates) != set(PRODUCTS) or any(
            not math.isfinite(value) or value <= 0 for value in rates.values()
        ):
            raise CapacityPlanningError(
                "Run rates must contain a positive value for every product."
            )


class ProductCapacityRecord(TypedDict):
    """One product-month constrained production allocation."""

    forecast_origin: str
    horizon_months: int
    period: str
    work_center_id: str
    work_center_name: str
    product_sku: str
    product_name: str
    base_production_requirement_units: int
    beginning_deferred_units: int
    total_requested_units: int
    run_rate_units_per_hour: float
    requested_run_hours: float
    capacity_factor: float
    planned_production_units: int
    planned_run_hours: float
    ending_deferred_units: int


class WorkCenterCapacityRecord(TypedDict):
    """One work-center-month load and availability calculation."""

    forecast_origin: str
    horizon_months: int
    period: str
    work_center_id: str
    work_center_name: str
    working_days: int
    shifts_per_day: int
    hours_per_shift: float
    regular_capacity_hours: float
    planned_downtime_percent: float
    overtime_hours: float
    effective_capacity_hours: float
    active_product_count: int
    required_setup_hours: float
    requested_run_hours: float
    required_hours: float
    required_utilization_percent: float
    capacity_gap_hours: float
    overloaded: bool
    capacity_factor: float
    scheduled_setup_hours: float
    scheduled_run_hours: float
    scheduled_hours: float
    unused_capacity_hours: float
    base_production_requirement_units: int
    beginning_deferred_units: int
    total_requested_units: int
    planned_production_units: int
    ending_deferred_units: int


@dataclass(frozen=True)
class CapacityPlan:
    """Product allocations and work-center load records for one plan."""

    products: list[ProductCapacityRecord]
    work_centers: list[WorkCenterCapacityRecord]


@dataclass(frozen=True)
class CapacityPlanSummary:
    """Key exception counts and output totals."""

    product_record_count: int
    work_center_record_count: int
    overloaded_work_center_months: int
    base_production_requirement_units: int
    planned_production_units: int
    ending_deferred_units: int
    maximum_required_utilization_percent: float


def default_capacity_policy() -> CapacityPolicy:
    """Return independent mappings for the approved default policy."""

    return CapacityPolicy(
        overtime_hours=dict(DEFAULT_OVERTIME_HOURS),
        run_rates=dict(DEFAULT_RUN_RATES),
    )


def build_capacity_plan(
    inventory_plan: Sequence[InventoryPlanRecord],
    policy: CapacityPolicy,
    *,
    forecast_origin: str,
    planning_horizon: int = DEFAULT_CAPACITY_HORIZON,
) -> CapacityPlan:
    """Allocate monthly production proportionally within each work center."""

    if planning_horizon < 1:
        raise CapacityPlanningError("Planning horizon must be at least one month.")
    indexed: dict[tuple[int, str], InventoryPlanRecord] = {}
    for record in inventory_plan:
        if record["forecast_origin"] != forecast_origin:
            continue
        key = (record["horizon_months"], record["product_sku"])
        if key in indexed:
            raise CapacityPlanningError(
                "Inventory requirements must be unique by horizon and product."
            )
        indexed[key] = record
    required = {
        (horizon, product_sku)
        for horizon in range(1, planning_horizon + 1)
        for product_sku in PRODUCTS
    }
    missing = sorted(required - set(indexed))
    if missing:
        horizon, product_sku = missing[0]
        raise CapacityPlanningError(
            f"Production horizon {horizon} for {product_sku} is unavailable."
        )

    deferred = {product_sku: 0 for product_sku in PRODUCTS}
    product_records: list[ProductCapacityRecord] = []
    work_center_records: list[WorkCenterCapacityRecord] = []
    regular_capacity = (
        policy.working_days_per_month
        * policy.shifts_per_day
        * policy.hours_per_shift
    )
    for horizon in range(1, planning_horizon + 1):
        period = indexed[(horizon, next(iter(PRODUCTS)))]["period"]
        for work_center_id, work_center_name in WORK_CENTERS.items():
            product_skus = [
                product_sku
                for product_sku in PRODUCTS
                if PRODUCT_WORK_CENTERS[product_sku] == work_center_id
            ]
            base = {
                product_sku: indexed[(horizon, product_sku)][
                    "net_production_requirement_units"
                ]
                for product_sku in product_skus
            }
            beginning_deferred = {
                product_sku: deferred[product_sku] for product_sku in product_skus
            }
            requested = {
                product_sku: base[product_sku] + beginning_deferred[product_sku]
                for product_sku in product_skus
            }
            active_count = sum(units > 0 for units in requested.values())
            required_setup = active_count * policy.setup_hours_per_active_product
            requested_run = sum(
                requested[product_sku] / policy.run_rates[product_sku]
                for product_sku in product_skus
            )
            effective_capacity = (
                regular_capacity * (1 - policy.planned_downtime_percent / 100)
                + policy.overtime_hours[work_center_id]
            )
            available_runtime = max(0.0, effective_capacity - required_setup)
            factor = (
                1.0
                if requested_run == 0
                else min(1.0, available_runtime / requested_run)
            )
            planned = {
                product_sku: math.floor(requested[product_sku] * factor + 1e-9)
                for product_sku in product_skus
            }
            planned_run = {
                product_sku: planned[product_sku] / policy.run_rates[product_sku]
                for product_sku in product_skus
            }
            for product_sku in product_skus:
                ending_deferred = requested[product_sku] - planned[product_sku]
                product_records.append(
                    ProductCapacityRecord(
                        forecast_origin=forecast_origin,
                        horizon_months=horizon,
                        period=period,
                        work_center_id=work_center_id,
                        work_center_name=work_center_name,
                        product_sku=product_sku,
                        product_name=PRODUCTS[product_sku],
                        base_production_requirement_units=base[product_sku],
                        beginning_deferred_units=beginning_deferred[product_sku],
                        total_requested_units=requested[product_sku],
                        run_rate_units_per_hour=policy.run_rates[product_sku],
                        requested_run_hours=(
                            requested[product_sku] / policy.run_rates[product_sku]
                        ),
                        capacity_factor=factor,
                        planned_production_units=planned[product_sku],
                        planned_run_hours=planned_run[product_sku],
                        ending_deferred_units=ending_deferred,
                    )
                )
                deferred[product_sku] = ending_deferred

            required_hours = required_setup + requested_run
            scheduled_setup = min(required_setup, effective_capacity)
            scheduled_run = sum(planned_run.values())
            scheduled_hours = scheduled_setup + scheduled_run
            work_center_records.append(
                WorkCenterCapacityRecord(
                    forecast_origin=forecast_origin,
                    horizon_months=horizon,
                    period=period,
                    work_center_id=work_center_id,
                    work_center_name=work_center_name,
                    working_days=policy.working_days_per_month,
                    shifts_per_day=policy.shifts_per_day,
                    hours_per_shift=policy.hours_per_shift,
                    regular_capacity_hours=regular_capacity,
                    planned_downtime_percent=policy.planned_downtime_percent,
                    overtime_hours=policy.overtime_hours[work_center_id],
                    effective_capacity_hours=effective_capacity,
                    active_product_count=active_count,
                    required_setup_hours=required_setup,
                    requested_run_hours=requested_run,
                    required_hours=required_hours,
                    required_utilization_percent=(
                        required_hours / effective_capacity * 100
                    ),
                    capacity_gap_hours=effective_capacity - required_hours,
                    overloaded=required_hours > effective_capacity,
                    capacity_factor=factor,
                    scheduled_setup_hours=scheduled_setup,
                    scheduled_run_hours=scheduled_run,
                    scheduled_hours=scheduled_hours,
                    unused_capacity_hours=max(
                        0.0, effective_capacity - scheduled_hours
                    ),
                    base_production_requirement_units=sum(base.values()),
                    beginning_deferred_units=sum(beginning_deferred.values()),
                    total_requested_units=sum(requested.values()),
                    planned_production_units=sum(planned.values()),
                    ending_deferred_units=sum(
                        deferred[product_sku] for product_sku in product_skus
                    ),
                )
            )
    return CapacityPlan(product_records, work_center_records)


def filter_capacity_products(
    records: Sequence[ProductCapacityRecord],
    *,
    product_sku: str | None = None,
) -> list[ProductCapacityRecord]:
    """Select constrained production records for one product."""

    if product_sku is not None and product_sku not in PRODUCTS:
        raise CapacityPlanningError(f"Unknown product SKU {product_sku!r}.")
    return [
        record
        for record in records
        if product_sku is None or record["product_sku"] == product_sku
    ]


def filter_work_centers(
    records: Sequence[WorkCenterCapacityRecord],
    *,
    work_center_id: str | None = None,
) -> list[WorkCenterCapacityRecord]:
    """Select capacity records for one work center."""

    if work_center_id is not None and work_center_id not in WORK_CENTERS:
        raise CapacityPlanningError(f"Unknown work center {work_center_id!r}.")
    return [
        record
        for record in records
        if work_center_id is None or record["work_center_id"] == work_center_id
    ]


def summarize_capacity_plan(plan: CapacityPlan) -> CapacityPlanSummary:
    """Summarize overloads, requested output, and ending deferred units."""

    final_deferred: dict[str, int] = {}
    for record in plan.products:
        final_deferred[record["product_sku"]] = record["ending_deferred_units"]
    return CapacityPlanSummary(
        product_record_count=len(plan.products),
        work_center_record_count=len(plan.work_centers),
        overloaded_work_center_months=sum(
            record["overloaded"] for record in plan.work_centers
        ),
        base_production_requirement_units=sum(
            record["base_production_requirement_units"] for record in plan.products
        ),
        planned_production_units=sum(
            record["planned_production_units"] for record in plan.products
        ),
        ending_deferred_units=sum(final_deferred.values()),
        maximum_required_utilization_percent=max(
            (
                record["required_utilization_percent"]
                for record in plan.work_centers
            ),
            default=0.0,
        ),
    )
