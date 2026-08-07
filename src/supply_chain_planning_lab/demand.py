"""Load, validate, filter, and summarize the static demand scenario."""

from collections.abc import Sequence
import csv
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Literal, TypedDict

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator, model_validator


DEMAND_FIELDS = (
    "period",
    "customer",
    "customer_type",
    "product_sku",
    "product_name",
    "gross_order_units",
    "cancelled_units",
    "demand_units",
    "unit",
)
DEMAND_DATA_PATH = Path(__file__).with_name("resources") / "static_demand.csv"
EXPECTED_PERIODS = tuple(
    f"{year}-{month:02d}" for year in (2024, 2025) for month in range(1, 13)
)
CUSTOMERS = {
    "Building Houses Company": "builder",
    "Building Supply Company": "distributor",
    "Building Remodeler": "remodeler",
}
PRODUCTS = {
    "WIN-2436": "24 x 36 Vinyl Window",
    "WIN-3648": "36 x 48 Vinyl Window",
    "DOOR-3680": "36 x 80 Insulated Exterior Door",
}


class DemandDataError(ValueError):
    """Raised when demand data violates the approved scenario."""


class DemandRecord(TypedDict):
    """One customer-product-month order record."""

    period: str
    customer: str
    customer_type: str
    product_sku: str
    product_name: str
    gross_order_units: int
    cancelled_units: int
    demand_units: int
    unit: str


class DemandRecordModel(BaseModel):
    """Runtime validation for one row in the static demand file."""

    model_config = ConfigDict(extra="forbid")

    period: str
    customer: str
    customer_type: Literal["builder", "distributor", "remodeler"]
    product_sku: str
    product_name: str
    gross_order_units: int
    cancelled_units: int
    demand_units: int
    unit: Literal["finished_units"]

    @field_validator("period")
    @classmethod
    def period_is_canonical_month(cls, value: str) -> str:
        """Require a zero-padded calendar month in YYYY-MM form."""

        _parse_period(value)
        return value

    @field_validator("gross_order_units", "cancelled_units", "demand_units")
    @classmethod
    def units_are_nonnegative(cls, value: int) -> int:
        """Demand quantities cannot be negative."""

        if value < 0:
            raise ValueError("must be zero or greater")
        return value

    @model_validator(mode="after")
    def approved_dimensions_and_calculation(self) -> "DemandRecordModel":
        """Match the approved catalog and verify the demand equation."""

        expected_customer_type = CUSTOMERS.get(self.customer)
        if expected_customer_type is None:
            raise ValueError(f"unknown customer {self.customer!r}")
        if self.customer_type != expected_customer_type:
            raise ValueError(
                f"customer type must be {expected_customer_type!r} for {self.customer!r}"
            )

        expected_product_name = PRODUCTS.get(self.product_sku)
        if expected_product_name is None:
            raise ValueError(f"unknown product SKU {self.product_sku!r}")
        if self.product_name != expected_product_name:
            raise ValueError(
                f"product name must be {expected_product_name!r} "
                f"for {self.product_sku!r}"
            )
        if self.cancelled_units > self.gross_order_units:
            raise ValueError("cancelled units cannot exceed gross order units")
        if self.demand_units != self.gross_order_units - self.cancelled_units:
            raise ValueError(
                "demand units must equal gross order units minus cancelled units"
            )
        return self

    def as_record(self) -> DemandRecord:
        """Convert the validated model to the public record shape."""

        return DemandRecord(**self.model_dump())


@dataclass(frozen=True)
class DemandSummary:
    """Additive order measures for a selected set of records."""

    record_count: int
    gross_order_units: int
    cancelled_units: int
    demand_units: int


def load_static_demand() -> list[DemandRecord]:
    """Load the packaged, version-controlled demand scenario."""

    records = read_demand_csv(DEMAND_DATA_PATH)
    _validate_complete_scenario(records)
    return records


def read_demand_csv(path: Path) -> list[DemandRecord]:
    """Read and validate one demand CSV without generating values."""

    with path.open(encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        actual_fields = tuple(reader.fieldnames or ())
        if actual_fields != DEMAND_FIELDS:
            expected = ",".join(DEMAND_FIELDS)
            received = ",".join(actual_fields) or "no header"
            raise DemandDataError(
                f"Expected demand CSV header {expected}; received {received}."
            )

        records: list[DemandRecord] = []
        seen: set[tuple[str, str, str]] = set()
        for line_number, row in enumerate(reader, start=2):
            try:
                model = DemandRecordModel.model_validate(row)
            except (ValidationError, DemandDataError) as exc:
                if isinstance(exc, ValidationError):
                    first_error = exc.errors(include_url=False)[0]
                    location = ".".join(str(part) for part in first_error["loc"])
                    detail = first_error["msg"]
                    field = location or "record"
                else:
                    field = "period"
                    detail = str(exc)
                raise DemandDataError(
                    f"Demand CSV line {line_number} has invalid {field}: {detail}."
                ) from exc

            record = model.as_record()
            key = (record["period"], record["customer"], record["product_sku"])
            if key in seen:
                raise DemandDataError(
                    "Demand CSV has duplicate period/customer/product at line "
                    f"{line_number}: {' / '.join(key)}."
                )
            seen.add(key)
            records.append(record)
    return records


def filter_demand(
    records: Sequence[DemandRecord],
    *,
    start_period: str | None = None,
    end_period: str | None = None,
    customer: str | None = None,
    product_sku: str | None = None,
) -> list[DemandRecord]:
    """Apply inclusive scenario filters in stable chronological order."""

    if start_period is not None:
        _parse_period(start_period)
    if end_period is not None:
        _parse_period(end_period)
    if start_period and end_period and start_period > end_period:
        raise DemandDataError("Start period must not be later than end period.")
    if customer is not None and customer not in CUSTOMERS:
        raise DemandDataError(f"Unknown customer {customer!r}.")
    if product_sku is not None and product_sku not in PRODUCTS:
        raise DemandDataError(f"Unknown product SKU {product_sku!r}.")

    return sorted(
        (
            record
            for record in records
            if (start_period is None or record["period"] >= start_period)
            and (end_period is None or record["period"] <= end_period)
            and (customer is None or record["customer"] == customer)
            and (product_sku is None or record["product_sku"] == product_sku)
        ),
        key=lambda record: (
            record["period"],
            record["customer"],
            record["product_sku"],
        ),
    )


def summarize_demand(records: Sequence[DemandRecord]) -> DemandSummary:
    """Sum the approved order fields without forecasting or allocation."""

    return DemandSummary(
        record_count=len(records),
        gross_order_units=sum(record["gross_order_units"] for record in records),
        cancelled_units=sum(record["cancelled_units"] for record in records),
        demand_units=sum(record["demand_units"] for record in records),
    )


def monthly_demand(records: Sequence[DemandRecord]) -> list[dict[str, str | int]]:
    """Aggregate selected internal demand by requested ship month."""

    totals: dict[str, int] = {}
    for record in records:
        totals[record["period"]] = totals.get(record["period"], 0) + record[
            "demand_units"
        ]
    return [
        {"period": period, "demand_units": units}
        for period, units in sorted(totals.items())
    ]


def _validate_complete_scenario(records: Sequence[DemandRecord]) -> None:
    """Require exactly one row for every approved scenario combination."""

    expected = {
        (period, customer, product_sku)
        for period in EXPECTED_PERIODS
        for customer in CUSTOMERS
        for product_sku in PRODUCTS
    }
    actual = {
        (record["period"], record["customer"], record["product_sku"])
        for record in records
    }
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    if missing or extra:
        details: list[str] = []
        if missing:
            details.append(f"{len(missing)} missing combination(s)")
        if extra:
            details.append(f"{len(extra)} unexpected combination(s)")
        raise DemandDataError("Static demand scenario is incomplete: " + "; ".join(details))


def _parse_period(value: str) -> date:
    """Parse one canonical YYYY-MM period."""

    try:
        parsed = date.fromisoformat(f"{value}-01")
    except ValueError as exc:
        raise DemandDataError(f"Invalid period {value!r}; expected YYYY-MM") from exc
    if parsed.strftime("%Y-%m") != value:
        raise DemandDataError(f"Invalid period {value!r}; expected YYYY-MM")
    return parsed
