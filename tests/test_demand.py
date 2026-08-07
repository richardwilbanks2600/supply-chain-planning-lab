import csv

import pytest

from supply_chain_planning_lab.demand import (
    DEMAND_FIELDS,
    DemandDataError,
    filter_demand,
    load_static_demand,
    monthly_demand,
    read_demand_csv,
    summarize_demand,
)


def test_static_demand_is_complete_fixed_and_internally_consistent() -> None:
    records = load_static_demand()

    assert len(records) == 216
    assert {record["period"] for record in records} == {
        f"{year}-{month:02d}"
        for year in (2024, 2025)
        for month in range(1, 13)
    }
    assert any(record["demand_units"] == 0 for record in records)
    assert all(
        record["demand_units"]
        == record["gross_order_units"] - record["cancelled_units"]
        for record in records
    )

    summary = summarize_demand(records)
    assert summary.gross_order_units == 12_471
    assert summary.cancelled_units == 68
    assert summary.demand_units == 12_403


def test_demand_filters_and_monthly_totals_are_additive() -> None:
    selected = filter_demand(
        load_static_demand(),
        start_period="2024-01",
        end_period="2024-02",
        customer="Building Houses Company",
        product_sku="WIN-2436",
    )

    assert [record["period"] for record in selected] == ["2024-01", "2024-02"]
    assert monthly_demand(selected) == [
        {"period": "2024-01", "demand_units": 84},
        {"period": "2024-02", "demand_units": 93},
    ]
    assert summarize_demand(selected).demand_units == 177


def test_demand_reader_rejects_an_incorrect_net_calculation(tmp_path) -> None:
    csv_path = tmp_path / "bad-demand.csv"
    row = {
        "period": "2024-01",
        "customer": "Building Houses Company",
        "customer_type": "builder",
        "product_sku": "WIN-2436",
        "product_name": "24 x 36 Vinyl Window",
        "gross_order_units": 120,
        "cancelled_units": 5,
        "demand_units": 116,
        "unit": "finished_units",
    }
    with csv_path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=DEMAND_FIELDS)
        writer.writeheader()
        writer.writerow(row)

    with pytest.raises(DemandDataError, match="gross order units minus"):
        read_demand_csv(csv_path)


def test_demand_reader_rejects_duplicate_scenario_keys(tmp_path) -> None:
    csv_path = tmp_path / "duplicate-demand.csv"
    row = {
        "period": "2024-01",
        "customer": "Building Houses Company",
        "customer_type": "builder",
        "product_sku": "WIN-2436",
        "product_name": "24 x 36 Vinyl Window",
        "gross_order_units": 120,
        "cancelled_units": 5,
        "demand_units": 115,
        "unit": "finished_units",
    }
    with csv_path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=DEMAND_FIELDS)
        writer.writeheader()
        writer.writerows((row, row))

    with pytest.raises(DemandDataError, match="duplicate period/customer/product"):
        read_demand_csv(csv_path)
