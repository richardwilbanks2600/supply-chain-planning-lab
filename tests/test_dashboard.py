from pathlib import Path

from streamlit.testing.v1 import AppTest

from supply_chain_planning_lab.dashboard import (
    _latest_change_label,
    _records_for_display,
)


def _records():
    return [
        {
            "series_id": "PERMIT",
            "period": "2026-01",
            "value": 100.0,
            "unit": "thousands_of_units_saar",
        },
        {
            "series_id": "PERMIT",
            "period": "2026-02",
            "value": 125.0,
            "unit": "thousands_of_units_saar",
        },
        {
            "series_id": "PERMIT",
            "period": "2026-03",
            "value": 115.0,
            "unit": "thousands_of_units_saar",
        },
    ]


def test_dashboard_helpers_filter_order_and_summarize_shared_records() -> None:
    records = _records()

    assert [
        record["period"]
        for record in _records_for_display(
            records, count=2, newest_first=True
        )
    ] == ["2026-03", "2026-02"]
    assert _latest_change_label(records) == "-10.0"


def test_dashboard_starts_without_contacting_fred(monkeypatch) -> None:
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    dashboard = (
        Path(__file__).parents[1]
        / "src"
        / "supply_chain_planning_lab"
        / "dashboard.py"
    )

    app = AppTest.from_file(str(dashboard)).run(timeout=10)

    assert not app.exception
    assert app.title[0].value == "Supply Chain Planning Lab"
