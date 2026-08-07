"""Local Streamlit interface for validated FRED observations."""

from datetime import date
import logging
import os
from typing import cast

from dotenv import load_dotenv
import streamlit as st

from supply_chain_planning_lab.api import FredApiError
from supply_chain_planning_lab.cli import DEFAULT_START_DATE, SERIES_ID
from supply_chain_planning_lab.demand import (
    CUSTOMERS,
    DEFAULT_LAG_MONTHS,
    PRODUCTS,
    DemandAssumptions,
    DemandDataError,
    DemandRecord,
    filter_demand,
    generate_demand,
    load_fred_snapshot,
    monthly_demand,
    summarize_demand,
)
from supply_chain_planning_lab.forecasting import (
    METHOD_LABELS,
    PRIMARY_METHOD,
    compare_baselines,
    filter_forecasts,
    summarize_forecasts,
)
from supply_chain_planning_lab.inspection import summarize_records
from supply_chain_planning_lab.logging_config import configure_logging
from supply_chain_planning_lab.output import processed_csv_text
from supply_chain_planning_lab.transform import DataTransformError, ProcessedObservation
from supply_chain_planning_lab.workflow import PlanningResult, fetch_planning_data

logger = logging.getLogger(__name__)


def main() -> None:
    """Render a browser interface over the same workflow used by the CLI."""

    st.set_page_config(
        page_title="Supply Chain Planning Lab",
        page_icon="📦",
        layout="wide",
    )
    load_dotenv()
    configure_logging(verbose=True, log_file=None)

    st.title("Supply Chain Planning Lab")
    st.write(
        "Translate a fixed FRED market history into an interactive fictional "
        "customer-demand scenario with visible assumptions."
    )
    demand_tab, forecast_tab, external_tab = st.tabs(
        ("Internal demand", "Forecast baselines", "External market indicator")
    )
    with demand_tab:
        demand_records = _render_internal_demand()
    with forecast_tab:
        if demand_records is not None:
            _render_forecast_baselines(demand_records)
    with external_tab:
        _render_external_indicator()


def _render_internal_demand() -> list[DemandRecord] | None:
    """Render a deterministic scenario from the fixed FRED snapshot."""

    st.header("FRED-driven internal demand")
    st.write(
        "The source is a fixed FRED PERMIT snapshot covering 2000 through 2025. "
        "Sliders change visible business assumptions; no random values are used."
    )
    st.caption(
        f"A permit month's seasonally adjusted annual pace drives demand "
        f"{DEFAULT_LAG_MONTHS} months later. Cancellations are assumed to be zero."
    )

    st.subheader("Scenario assumptions")
    market_share_percent = st.slider(
        "Company market share (%)",
        min_value=0.01,
        max_value=1.00,
        value=0.10,
        step=0.01,
        format="%.2f%%",
        help="Share of the national monthly housing pace addressable by the company.",
    )
    allocation_cuts = st.slider(
        "Customer allocation boundaries (%)",
        min_value=0,
        max_value=100,
        value=(50, 80),
        step=1,
        help=(
            "First handle allocates Building Houses Company. The distance between "
            "handles allocates Building Supply Company. The remainder goes to "
            "Building Remodeler."
        ),
    )
    houses_percent, cumulative_supply_percent = allocation_cuts
    supply_percent = cumulative_supply_percent - houses_percent
    remodeler_percent = 100 - cumulative_supply_percent
    allocations = {
        "Building Houses Company": houses_percent / 100,
        "Building Supply Company": supply_percent / 100,
        "Building Remodeler": remodeler_percent / 100,
    }
    st.caption(
        "Allocation: "
        f"Building Houses Company {houses_percent}% | "
        f"Building Supply Company {supply_percent}% | "
        f"Building Remodeler {remodeler_percent}%"
    )

    small_window, large_window, exterior_door = st.columns(3)
    with small_window:
        win_2436 = st.slider("24 x 36 windows per home", 0, 20, 6, 1)
    with large_window:
        win_3648 = st.slider("36 x 48 windows per home", 0, 20, 4, 1)
    with exterior_door:
        door_3680 = st.slider("Exterior doors per home", 0, 5, 1, 1)

    assumptions = DemandAssumptions(
        market_share_percent=market_share_percent,
        customer_allocations=allocations,
        units_per_home={
            "WIN-2436": float(win_2436),
            "WIN-3648": float(win_3648),
            "DOOR-3680": float(door_3680),
        },
    )
    try:
        fred_records = load_fred_snapshot()
        records = generate_demand(fred_records, assumptions)
    except (OSError, UnicodeError, DemandDataError) as exc:
        logger.error("FRED-driven demand could not be calculated: %s", exc)
        st.error(f"FRED-driven demand could not be calculated: {exc}")
        return None

    customer_choice = st.selectbox(
        "Demand customer", ("All customers", *CUSTOMERS)
    )
    product_choice = st.selectbox(
        "Demand product", ("All products", *PRODUCTS)
    )
    selected = filter_demand(
        records,
        customer=None if customer_choice == "All customers" else customer_choice,
        product_sku=None if product_choice == "All products" else product_choice,
    )
    summary = summarize_demand(selected)

    source, months, demand = st.columns(3)
    source.metric("FRED source months", len(fred_records))
    months.metric("Derived demand months", len({row["period"] for row in selected}))
    demand.metric("Internal demand units", f"{summary.demand_units:,}")

    st.subheader("FRED PERMIT source")
    st.line_chart(
        [
            {"period": record["period"], "permit_saar": record["value"]}
            for record in fred_records
        ],
        x="period",
        y="permit_saar",
    )
    st.caption("Thousands of housing units at a seasonally adjusted annual rate.")

    st.subheader("Monthly internal demand")
    st.line_chart(monthly_demand(selected), x="period", y="demand_units")

    st.subheader("Order details")
    st.dataframe(
        selected,
        hide_index=True,
        width="stretch",
        column_config={
            "period": "Requested ship month",
            "fred_period": "Source FRED month",
            "fred_value_saar_thousands": st.column_config.NumberColumn(
                "FRED value (thousands, SAAR)", format="%.1f"
            ),
            "monthly_housing_pace": st.column_config.NumberColumn(
                "Monthly housing pace", format="%.1f"
            ),
            "company_market_share_percent": st.column_config.NumberColumn(
                "Company share (%)", format="%.2f"
            ),
            "customer": "Customer",
            "customer_type": "Customer type",
            "customer_allocation_percent": st.column_config.NumberColumn(
                "Customer allocation (%)", format="%.1f"
            ),
            "product_sku": "Product SKU",
            "product_name": "Product",
            "units_per_home": st.column_config.NumberColumn(
                "Units per home", format="%.1f"
            ),
            "demand_units": st.column_config.NumberColumn(
                "Internal demand", format="%d"
            ),
            "unit": "Unit",
        },
    )
    return records


def _render_forecast_baselines(demand_records: list[DemandRecord]) -> None:
    """Compare approved baseline forecasts for the current demand scenario."""

    st.header("Baseline forecast comparison")
    st.write(
        "Each method forecasts monthly product demand using only earlier internal "
        "demand. The common evaluation period is January 2020 through December 2025."
    )
    st.caption(
        "Error = actual - forecast. Positive error means demand was underforecast; "
        "negative error means it was overforecast."
    )
    records, summaries = compare_baselines(demand_records)
    st.subheader("Method performance")
    st.caption(
        "Primary baseline identifies the approved reference method; it does not "
        "claim that the method has the lowest error."
    )
    st.dataframe(
        [
            {
                "method": summary.method_label,
                "forecast_count": summary.forecast_count,
                "mae": summary.mean_absolute_error,
                "bias": summary.bias,
                "primary": "Yes" if summary.method == PRIMARY_METHOD else "No",
            }
            for summary in summaries
        ],
        hide_index=True,
        width="stretch",
        column_config={
            "method": "Method",
            "forecast_count": "Forecasts",
            "mae": st.column_config.NumberColumn("MAE", format="%.1f"),
            "bias": st.column_config.NumberColumn("Bias", format="%+.1f"),
            "primary": "Primary baseline",
        },
    )

    method = st.selectbox(
        "Forecast method",
        tuple(METHOD_LABELS),
        index=tuple(METHOD_LABELS).index(PRIMARY_METHOD),
        format_func=lambda value: METHOD_LABELS[value],
    )
    product_sku = st.selectbox(
        "Forecast product",
        tuple(PRODUCTS),
        format_func=lambda value: f"{value} - {PRODUCTS[value]}",
    )
    selected = filter_forecasts(
        records,
        method=method,
        product_sku=product_sku,
    )
    summary = summarize_forecasts(selected, method)
    count, mae, bias = st.columns(3)
    count.metric("Forecast observations", summary.forecast_count)
    mae.metric(
        "Mean absolute error",
        f"{summary.mean_absolute_error:,.1f}"
        if summary.mean_absolute_error is not None
        else "Not available",
    )
    bias.metric(
        "Mean error (bias)",
        f"{summary.bias:+,.1f}" if summary.bias is not None else "Not available",
    )

    st.subheader("Actual versus forecast")
    st.line_chart(
        [
            {
                "period": record["period"],
                "actual_units": record["actual_units"],
                "forecast_units": record["forecast_units"],
            }
            for record in selected
        ],
        x="period",
        y=("actual_units", "forecast_units"),
    )
    st.dataframe(
        selected,
        hide_index=True,
        width="stretch",
        column_config={
            "period": "Month",
            "product_sku": "Product SKU",
            "product_name": "Product",
            "method": None,
            "method_label": "Method",
            "actual_units": "Actual units",
            "forecast_units": st.column_config.NumberColumn(
                "Forecast units", format="%.1f"
            ),
            "error_units": st.column_config.NumberColumn(
                "Error", format="%+.1f"
            ),
            "absolute_error_units": st.column_config.NumberColumn(
                "Absolute error", format="%.1f"
            ),
        },
    )

    with st.expander("How the trailing 3-month average works"):
        st.code(
            "forecast(t) = [actual(t-1) + actual(t-2) + actual(t-3)] / 3",
            language="text",
        )
        st.write(
            "A three-month window smooths short-term movement but can lag when "
            "demand rises or falls for several months. The future Learning Guide "
            "will compare other window lengths, weighted averages, and exponential "
            "averages."
        )


def _render_external_indicator() -> None:
    """Render the separately loaded FRED indicator workflow."""

    st.header("External market indicator")
    st.info(
        "Building permits are an external market indicator. They are not "
        "customer orders or a company demand forecast."
    )

    with st.form("fred-request"):
        start_date = st.date_input(
            "First observation date",
            value=date.fromisoformat(DEFAULT_START_DATE),
        )
        submitted = st.form_submit_button("Load validated FRED data")

    if submitted:
        _load_result(start_date)

    if "planning_result" not in st.session_state:
        st.caption(
            "Choose a start date and load data. Your FRED API key is read from "
            "the local environment and is never displayed."
        )
        return

    result = cast(PlanningResult, st.session_state["planning_result"])
    _render_result(result)


def _load_result(start_date: date) -> None:
    """Fetch one response and retain only a successfully validated result."""

    api_key = os.environ.get("FRED_API_KEY", "").strip()
    if not api_key:
        st.error(
            "FRED_API_KEY is not configured. Add it to a local .env file before "
            "loading data."
        )
        return

    try:
        with st.spinner("Requesting and validating FRED data..."):
            result = fetch_planning_data(
                api_key=api_key,
                series_id=SERIES_ID,
                observation_start=start_date.isoformat(),
            )
    except (FredApiError, DataTransformError) as exc:
        logger.warning("Dashboard request could not be completed: %s", exc)
        st.error(str(exc))
        return

    st.session_state["planning_result"] = result
    st.session_state["start_date"] = start_date


def _render_result(result: PlanningResult) -> None:
    """Display summaries, exploration controls, a chart, and trusted rows."""

    records = list(result.records)
    summary = summarize_records(records)
    st.subheader("Validated observations")

    total, missing, latest, change = st.columns(4)
    total.metric("Valid observations", len(records))
    missing.metric("Missing values skipped", result.skipped_missing)
    latest.metric(
        "Latest observation",
        f"{records[-1]['value']:,.1f}" if records else "None",
        help="Thousands of units at a seasonally adjusted annual rate.",
    )
    change.metric(
        "Latest valid-observation change",
        _latest_change_label(records),
        help="Latest value minus the preceding valid observation; gaps may span months.",
    )

    minimum, maximum, trailing_average = st.columns(3)
    minimum.metric(
        "Minimum",
        f"{summary.minimum:,.1f}" if summary.minimum is not None else "None",
    )
    maximum.metric(
        "Maximum",
        f"{summary.maximum:,.1f}" if summary.maximum is not None else "None",
    )
    trailing_average.metric(
        f"Trailing average ({summary.trailing_count})",
        (
            f"{summary.trailing_average:,.1f}"
            if summary.trailing_average is not None
            else "None"
        ),
        help="Arithmetic mean of up to the latest 12 valid observations; not a forecast.",
    )

    st.download_button(
        "Download raw FRED JSON",
        data=result.raw_text,
        file_name="fred-permit-raw.json",
        mime="application/json",
    )
    st.download_button(
        "Download validated observations as CSV",
        data=processed_csv_text(records),
        file_name="fred-permit-processed.csv",
        mime="text/csv",
    )

    if not records:
        st.warning("FRED returned no usable observations for this request.")
        return

    count = int(
        st.number_input(
            "Recent observations to display",
            min_value=1,
            max_value=len(records),
            value=min(24, len(records)),
            step=1,
        )
    )
    order = st.selectbox("Table order", ("Newest first", "Oldest first"))
    displayed = _records_for_display(records, count=count, newest_first=order == "Newest first")
    chart_records = sorted(displayed, key=lambda record: record["period"])

    st.subheader("Permit indicator over time")
    st.line_chart(chart_records, x="period", y="value")

    st.subheader("Observation details")
    st.dataframe(
        displayed,
        hide_index=True,
        width="stretch",
        column_config={
            "series_id": "Series",
            "period": "Month",
            "value": st.column_config.NumberColumn(
                "Value (thousands, SAAR)", format="%.1f"
            ),
            "unit": "Unit",
        },
    )


def _records_for_display(
    records: list[ProcessedObservation], *, count: int, newest_first: bool
) -> list[ProcessedObservation]:
    """Select the latest observations and apply the requested table order."""

    selected = records[-count:]
    return list(reversed(selected)) if newest_first else selected


def _latest_change_label(records: list[ProcessedObservation]) -> str:
    """Format the difference between the two most recent usable observations."""

    change = summarize_records(records).latest_change
    if change is None:
        return "Not available"
    return f"{change:+,.1f}"


if __name__ == "__main__":
    main()
