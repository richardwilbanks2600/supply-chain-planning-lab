"""Tests for the maintained learner-content registry."""

from supply_chain_planning_lab.learning import (
    FORECAST_METHOD_LESSONS,
    TERMS,
    TEXTBOOK_NAME,
    TEXTBOOK_VERSION,
    help_text,
    learning_sections,
    learning_term,
    search_learning_terms,
)


def test_registry_keys_are_unique_and_cover_the_planning_workflow() -> None:
    """Require broad coverage across every integrated planning layer."""

    assert len(TERMS) >= 50
    assert len({item.key for item in TERMS}) == len(TERMS)
    assert set(learning_sections()) >= {
        "Source data",
        "Demand",
        "Forecasting",
        "Inventory",
        "Procurement",
        "Supplier performance",
        "Capacity",
    }
    assert help_text("mae") == learning_term("mae").short
    assert "realized demand - forecast demand" in learning_term("forecast_error").formula
    assert learning_term("fred_expected_demand").section == "Demand"
    assert "0.75 and 1.25" in learning_term("demand_realization_factor").detail
    assert learning_term("baseline_scenario").dashboard_tab == "Overview"
    assert "fictional" in learning_term("generated_backtest_actual").short.lower()
    assert learning_term("projected_ending_inventory").formula == (
        "inventory position + net production requirement - forecast demand"
    )
    assert {"standard_deviation", "variance", "service_factor", "smoothing_alpha"} <= {
        item.key for item in TERMS
    }


def test_search_matches_terms_formulas_keywords_and_sections() -> None:
    """Make search forgiving without depending on an external service."""

    assert [item.key for item in search_learning_terms("OTIF")] == [
        "otif",
        "risk_adjusted_receipt",
    ]
    assert any(item.key == "deferred_production" for item in search_learning_terms("backlog"))
    capacity = search_learning_terms("hours", section="Capacity")
    assert capacity
    assert all(item.section == "Capacity" for item in capacity)
    assert search_learning_terms("term that does not exist") == []
    assert any(
        item.key == "standard_deviation"
        for item in search_learning_terms("spread from their average")
    )


def test_forecast_lessons_and_minimal_textbook_credit_are_explicit() -> None:
    """Protect the approved teaching comparison and concise credit wording."""

    names = {item.name for item in FORECAST_METHOD_LESSONS}
    assert "3-month simple moving average" in names
    assert "Weighted moving average" in names
    assert "Simple exponential smoothing" in names
    assert TEXTBOOK_NAME == "Operations and Supply Chain Management"
    assert TEXTBOOK_VERSION == "7th Edition"
