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
    headers = {header.value for header in app.header}
    assert "Start here: follow one planning story" in headers
    assert "1. Where does company demand come from?" in headers
    assert "2. What do we think will happen next?" in headers
    assert "3. How much finished product should we make?" in headers
    assert "4. What materials should we purchase, and when?" in headers
    assert "5. What can the factory actually build?" in headers
    assert any(
        metric.label == "Fictional internal demand units" for metric in app.metric
    )
    assert any(metric.label == "Mean absolute error" for metric in app.metric)
    assert any(slider.label == "Company market share (%)" for slider in app.slider)
    assert any(selectbox.label == "Forecast method" for selectbox in app.selectbox)
    assert any(
        selectbox.label == "FRED-informed forecast product"
        for selectbox in app.selectbox
    )
    assert any(
        slider.label == "FRED-informed demand horizon (months)"
        for slider in app.slider
    )
    assert any(
        slider.label == "Finished-goods safety stock (%)"
        for slider in app.slider
    )
    assert any(
        selectbox.label == "Forecast starting point"
        for selectbox in app.selectbox
    )
    assert any(
        metric.label == "Unconstrained production requirement"
        for metric in app.metric
    )
    assert any(
        selectbox.label == "Material safety-stock method"
        for selectbox in app.selectbox
    )
    assert any(
        selectbox.label == "How should open supplier orders be counted?"
        for selectbox in app.selectbox
    )
    assert any(metric.label == "Material purchase actions" for metric in app.metric)
    assert any(slider.label == "Working days per month" for slider in app.slider)
    assert any(slider.label == "Planned downtime (%)" for slider in app.slider)
    assert any(
        selectbox.label == "Work center to explore" for selectbox in app.selectbox
    )
    assert any(
        metric.label == "Overloaded work-center months" for metric in app.metric
    )


def test_market_share_slider_recalculates_internal_demand(monkeypatch) -> None:
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    dashboard = (
        Path(__file__).parents[1]
        / "src"
        / "supply_chain_planning_lab"
        / "dashboard.py"
    )
    app = AppTest.from_file(str(dashboard)).run(timeout=10)
    baseline = next(
        metric.value
        for metric in app.metric
        if metric.label == "Fictional internal demand units"
    )

    market_share = next(
        slider for slider in app.slider if slider.label == "Company market share (%)"
    )
    market_share.set_value(0.20).run(timeout=10)

    changed = next(
        metric.value
        for metric in app.metric
        if metric.label == "Fictional internal demand units"
    )
    changed_units = int(changed.replace(",", ""))
    baseline_units = int(baseline.replace(",", ""))
    # Whole-unit rounding can differ once for each of 309 months x 3 products.
    assert abs(changed_units - baseline_units * 2) <= 927

    reset = next(
        button
        for button in app.button
        if button.label == "Reset all assumptions to defaults"
    )
    reset.click().run(timeout=10)
    restored = next(
        metric.value
        for metric in app.metric
        if metric.label == "Fictional internal demand units"
    )
    assert restored == baseline
