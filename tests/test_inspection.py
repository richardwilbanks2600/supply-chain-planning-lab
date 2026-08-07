from pathlib import Path

import pytest

from supply_chain_planning_lab.inspection import (
    ProcessedDataError,
    filter_records,
    inspect_quality,
    read_processed_csv,
    summarize_records,
)
from supply_chain_planning_lab.output import write_processed_csv


def _example_records():
    return [
        {
            "series_id": "PERMIT",
            "period": "2026-01",
            "value": 100.0,
            "unit": "thousands_of_units_saar",
        },
        {
            "series_id": "PERMIT",
            "period": "2026-03",
            "value": 120.0,
            "unit": "thousands_of_units_saar",
        },
        {
            "series_id": "PERMIT",
            "period": "2026-04",
            "value": 140.0,
            "unit": "thousands_of_units_saar",
        },
    ]


def test_read_quality_filter_and_summary_match_the_manual_example(tmp_path) -> None:
    csv_path = tmp_path / "processed.csv"
    write_processed_csv(csv_path, _example_records())

    records = read_processed_csv(csv_path)
    report = inspect_quality(records)
    selected = filter_records(
        records, start_period="2026-03", end_period="2026-04"
    )
    full_summary = summarize_records(records)

    assert report.status == "WARNING"
    assert report.chronological is True
    assert report.duplicate_periods == ()
    assert report.missing_periods == ("2026-02",)
    assert [record["period"] for record in selected] == ["2026-03", "2026-04"]
    assert full_summary.minimum == 100.0
    assert full_summary.maximum == 140.0
    assert full_summary.latest == 140.0
    assert full_summary.latest_change == 20.0
    assert full_summary.trailing_average == 120.0
    assert full_summary.trailing_count == 3


def test_quality_fails_duplicates_and_warns_about_source_order() -> None:
    records = [_example_records()[1], _example_records()[0], _example_records()[1]]

    report = inspect_quality(records)

    assert report.status == "FAIL"
    assert report.chronological is False
    assert report.duplicate_periods == ("2026-03",)
    assert report.missing_periods == ("2026-02",)


@pytest.mark.parametrize(
    ("row", "message"),
    [
        ("PERMIT,2026-13,100.0,thousands_of_units_saar\n", "period"),
        ("PERMIT,2026-01,nan,thousands_of_units_saar\n", "value"),
        ("OTHER,2026-01,100.0,thousands_of_units_saar\n", "series_id"),
        ("PERMIT,2026-01,100.0,units\n", "unit"),
    ],
)
def test_read_processed_csv_rejects_malformed_rows(
    tmp_path: Path, row: str, message: str
) -> None:
    csv_path = tmp_path / "malformed.csv"
    csv_path.write_text(
        "series_id,period,value,unit\n" + row,
        encoding="utf-8",
    )

    with pytest.raises(ProcessedDataError, match=message):
        read_processed_csv(csv_path)


def test_read_processed_csv_rejects_an_unexpected_header(tmp_path: Path) -> None:
    csv_path = tmp_path / "wrong-header.csv"
    csv_path.write_text("period,value\n2026-01,100.0\n", encoding="utf-8")

    with pytest.raises(ProcessedDataError, match="Expected CSV header"):
        read_processed_csv(csv_path)


def test_filter_rejects_an_inverted_range() -> None:
    with pytest.raises(ProcessedDataError, match="Start period"):
        filter_records(
            _example_records(), start_period="2026-04", end_period="2026-01"
        )


def test_empty_and_single_record_summaries_are_explicit() -> None:
    empty = summarize_records([])
    single = summarize_records(_example_records()[:1])

    assert empty.latest is None
    assert empty.trailing_count == 0
    assert single.latest == 100.0
    assert single.latest_change is None
    assert single.trailing_average == 100.0
