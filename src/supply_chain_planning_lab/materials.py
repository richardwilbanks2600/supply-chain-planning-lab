"""Fictional material catalog, BOM, open orders, and supplier history."""

from collections import defaultdict
from collections.abc import Sequence
import csv
from dataclasses import dataclass
from pathlib import Path
from statistics import fmean, stdev
from typing import TypedDict

from .demand import PRODUCTS
from .inventory import InventoryPlanRecord


SUPPLIER_HISTORY_PATH = (
    Path(__file__).with_name("resources") / "supplier_delivery_history.csv"
)


class MaterialDataError(ValueError):
    """Raised when material or supplier teaching data is invalid."""


@dataclass(frozen=True)
class Component:
    """One purchased component and its approved primary supplier."""

    sku: str
    name: str
    unit: str
    supplier_id: str
    supplier_name: str
    planned_lead_months: int


COMPONENTS = {
    "GLASS-SQFT": Component(
        "GLASS-SQFT", "Window glass", "square_feet", "CLEARVIEW",
        "ClearView Glass", 2,
    ),
    "VINYL-LNFT": Component(
        "VINYL-LNFT", "Vinyl frame extrusion", "linear_feet", "VINYLWORKS",
        "VinylWorks", 1,
    ),
    "WINDOW-HARDWARE-KIT": Component(
        "WINDOW-HARDWARE-KIT", "Window hardware kit", "kits",
        "RELIABLE_HARDWARE", "Reliable Hardware", 1,
    ),
    "DOOR-SLAB": Component(
        "DOOR-SLAB", "Insulated door slab", "each", "SOLIDCORE",
        "SolidCore Doors", 2,
    ),
    "DOOR-FRAME-KIT": Component(
        "DOOR-FRAME-KIT", "Door frame kit", "kits", "FRAMESOURCE",
        "FrameSource", 1,
    ),
    "DOOR-HARDWARE-KIT": Component(
        "DOOR-HARDWARE-KIT", "Door hardware kit", "kits", "ENTRY_HARDWARE",
        "Entry Hardware Co.", 1,
    ),
}

# Each tuple is (component SKU, quantity per finished unit).
BOM = {
    "WIN-2436": (
        ("GLASS-SQFT", 6.0),
        ("VINYL-LNFT", 10.0),
        ("WINDOW-HARDWARE-KIT", 1.0),
    ),
    "WIN-3648": (
        ("GLASS-SQFT", 12.0),
        ("VINYL-LNFT", 14.0),
        ("WINDOW-HARDWARE-KIT", 1.0),
    ),
    "DOOR-3680": (
        ("DOOR-SLAB", 1.0),
        ("DOOR-FRAME-KIT", 1.0),
        ("DOOR-HARDWARE-KIT", 1.0),
    ),
}

DEFAULT_MATERIAL_INVENTORY = {
    "GLASS-SQFT": 5_000,
    "VINYL-LNFT": 7_000,
    "WINDOW-HARDWARE-KIT": 600,
    "DOOR-SLAB": 100,
    "DOOR-FRAME-KIT": 100,
    "DOOR-HARDWARE-KIT": 100,
}

# Fixed quantities received at horizons relative to the selected plan origin.
OPEN_ORDER_RECEIPTS = (
    (1, "GLASS-SQFT", 4_000),
    (2, "GLASS-SQFT", 3_000),
    (1, "VINYL-LNFT", 5_000),
    (1, "WINDOW-HARDWARE-KIT", 400),
    (1, "DOOR-SLAB", 50),
    (1, "DOOR-FRAME-KIT", 50),
    (1, "DOOR-HARDWARE-KIT", 50),
)


class MaterialRequirementRecord(TypedDict):
    """One aggregated component requirement for one production month."""

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


@dataclass(frozen=True)
class SupplierDelivery:
    """One validated fictional supplier delivery."""

    supplier_id: str
    component_sku: str
    delivery_id: str
    promised_lead_months: int
    actual_lead_months: int
    ordered_quantity: int
    received_quantity: int

    @property
    def on_time(self) -> bool:
        return self.actual_lead_months <= self.promised_lead_months

    @property
    def in_full(self) -> bool:
        return self.received_quantity >= self.ordered_quantity


@dataclass(frozen=True)
class SupplierPerformance:
    """Delivery reliability measures for one component's supplier."""

    supplier_id: str
    supplier_name: str
    component_sku: str
    delivery_count: int
    average_actual_lead_months: float
    lead_time_standard_deviation: float
    on_time_rate: float
    fill_rate: float
    otif_rate: float


def explode_material_requirements(
    inventory_plan: Sequence[InventoryPlanRecord],
) -> list[MaterialRequirementRecord]:
    """Translate net finished-goods production through the approved BOM."""

    if set(BOM) != set(PRODUCTS):
        raise MaterialDataError("BOM must cover every approved product.")
    grouped: dict[tuple[str, int, str, str], dict[str, int]] = defaultdict(dict)
    for record in inventory_plan:
        product_sku = record["product_sku"]
        if product_sku not in BOM:
            raise MaterialDataError(f"BOM is unavailable for {product_sku}.")
        production = record["net_production_requirement_units"]
        for component_sku, quantity_per in BOM[product_sku]:
            component_units = round(production * quantity_per)
            key = (
                record["forecast_origin"],
                record["horizon_months"],
                record["period"],
                component_sku,
            )
            grouped[key][product_sku] = component_units

    requirements: list[MaterialRequirementRecord] = []
    for key, production_sources in grouped.items():
        origin, horizon, period, component_sku = key
        component = COMPONENTS[component_sku]
        requirements.append(
            MaterialRequirementRecord(
                forecast_origin=origin,
                horizon_months=horizon,
                period=period,
                component_sku=component_sku,
                component_name=component.name,
                unit=component.unit,
                supplier_id=component.supplier_id,
                supplier_name=component.supplier_name,
                planned_lead_months=component.planned_lead_months,
                gross_requirement_units=sum(production_sources.values()),
                production_source_units=production_sources,
            )
        )
    return sorted(
        requirements,
        key=lambda record: (record["horizon_months"], record["component_sku"]),
    )


def load_supplier_history() -> list[SupplierDelivery]:
    """Load and validate the packaged fictional delivery history."""

    expected_fields = (
        "supplier_id",
        "component_sku",
        "delivery_id",
        "promised_lead_months",
        "actual_lead_months",
        "ordered_quantity",
        "received_quantity",
    )
    try:
        with SUPPLIER_HISTORY_PATH.open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            if tuple(reader.fieldnames or ()) != expected_fields:
                raise MaterialDataError("Supplier history columns are invalid.")
            deliveries = []
            for row_number, row in enumerate(reader, start=2):
                try:
                    delivery = SupplierDelivery(
                        supplier_id=row["supplier_id"],
                        component_sku=row["component_sku"],
                        delivery_id=row["delivery_id"],
                        promised_lead_months=int(row["promised_lead_months"]),
                        actual_lead_months=int(row["actual_lead_months"]),
                        ordered_quantity=int(row["ordered_quantity"]),
                        received_quantity=int(row["received_quantity"]),
                    )
                except (TypeError, ValueError) as exc:
                    raise MaterialDataError(
                        f"Supplier history row {row_number} contains invalid numbers."
                    ) from exc
                _validate_delivery(delivery, row_number)
                deliveries.append(delivery)
    except OSError as exc:
        raise MaterialDataError(f"Supplier history could not be read: {exc}") from exc

    if len(deliveries) != 36:
        raise MaterialDataError("Supplier history must contain 36 deliveries.")
    counts = defaultdict(int)
    for delivery in deliveries:
        counts[delivery.component_sku] += 1
    if set(counts) != set(COMPONENTS) or any(count != 6 for count in counts.values()):
        raise MaterialDataError(
            "Supplier history must contain six deliveries for every component."
        )
    return deliveries


def summarize_supplier_performance(
    deliveries: Sequence[SupplierDelivery],
) -> list[SupplierPerformance]:
    """Calculate reliability measures by component and supplier."""

    grouped: dict[str, list[SupplierDelivery]] = defaultdict(list)
    for delivery in deliveries:
        grouped[delivery.component_sku].append(delivery)
    summaries: list[SupplierPerformance] = []
    for component_sku, component in COMPONENTS.items():
        selected = grouped.get(component_sku, [])
        if not selected:
            raise MaterialDataError(
                f"Supplier history is unavailable for {component_sku}."
            )
        lead_times = [delivery.actual_lead_months for delivery in selected]
        summaries.append(
            SupplierPerformance(
                supplier_id=component.supplier_id,
                supplier_name=component.supplier_name,
                component_sku=component_sku,
                delivery_count=len(selected),
                average_actual_lead_months=fmean(lead_times),
                lead_time_standard_deviation=(
                    stdev(lead_times) if len(lead_times) > 1 else 0.0
                ),
                on_time_rate=fmean(
                    1.0 if delivery.on_time else 0.0 for delivery in selected
                ),
                fill_rate=(
                    sum(delivery.received_quantity for delivery in selected)
                    / sum(delivery.ordered_quantity for delivery in selected)
                ),
                otif_rate=fmean(
                    1.0 if delivery.on_time and delivery.in_full else 0.0
                    for delivery in selected
                ),
            )
        )
    return summaries


def _validate_delivery(delivery: SupplierDelivery, row_number: int) -> None:
    """Reject supplier rows that cannot support the approved measures."""

    component = COMPONENTS.get(delivery.component_sku)
    if component is None or component.supplier_id != delivery.supplier_id:
        raise MaterialDataError(
            f"Supplier history row {row_number} has an unknown pairing."
        )
    if (
        delivery.promised_lead_months < 1
        or delivery.actual_lead_months < 1
        or delivery.ordered_quantity <= 0
        or delivery.received_quantity < 0
    ):
        raise MaterialDataError(
            f"Supplier history row {row_number} contains invalid values."
        )
