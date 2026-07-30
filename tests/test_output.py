import csv
from datetime import datetime, timezone

from supply_chain_planning_lab.output import (
    create_output_paths,
    processed_csv_text,
    write_processed_csv,
    write_raw_response,
)


def test_output_files_preserve_raw_text_and_write_inspectable_csv(tmp_path) -> None:
    paths = create_output_paths(
        tmp_path,
        now=datetime(2026, 7, 20, 18, 30, tzinfo=timezone.utc),
    )
    raw_text = '{"observations": []}'
    records = [
        {
            "series_id": "PERMIT",
            "period": "2026-06",
            "value": 1367.0,
            "unit": "thousands_of_units_saar",
        }
    ]

    write_raw_response(paths.raw, raw_text)
    write_processed_csv(paths.processed, records)

    assert paths.raw.name == "fred_permit_20260720T183000Z.json"
    assert paths.raw.read_text(encoding="utf-8") == raw_text
    with paths.processed.open(encoding="utf-8", newline="") as csv_file:
        assert list(csv.DictReader(csv_file)) == [
            {
                "series_id": "PERMIT",
                "period": "2026-06",
                "value": "1367.0",
                "unit": "thousands_of_units_saar",
            }
        ]
    assert "series_id,period,value,unit" in processed_csv_text(records)
