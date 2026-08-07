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
    PRODUCTS,
    DemandDataError,
    filter_demand,
    load_static_demand,
    monthly_demand,
    summarize_demand,
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
        "Compare a fixed fictional customer-demand scenario with a separately "
        "validated external construction-market indicator."
    )
    demand_tab, external_tab = st.tabs(
        ("Internal demand", "External market indicator")
    )
    with demand_tab:
        _render_internal_demand()
    with external_tab:
        _render_external_indicator()


def _render_internal_demand() -> None:
    """Render the validated static scenario without contacting FRED."""

    st.header("Static internal demand")
    st.write(
        "These fictional order records are stored in a version-controlled CSV. "
        "Dashboard reruns load the same values; they do not generate demand."
    )
    st.caption(
        "Internal demand = gross ordered units - cancelled units, assigned to "
        "the customer's requested ship month."
    )
    try:
        records = load_static_demand()
    except (OSError, UnicodeError, DemandDataError) as exc:
        logger.error("Static demand could not be loaded: %s", exc)
        st.error(f"Static demand could not be loaded: {exc}")
        return

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

    gross, cancelled, demand = st.columns(3)
    gross.metric("Gross ordered units", f"{summary.gross_order_units:,}")
    cancelled.metric("Cancelled units", f"{summary.cancelled_units:,}")
    demand.metric("Internal demand units", f"{summary.demand_units:,}")

    st.subheader("Monthly internal demand")
    st.line_chart(monthly_demand(selected), x="period", y="demand_units")

    st.subheader("Order details")
    st.dataframe(
        selected,
        hide_index=True,
        width="stretch",
        column_config={
            "period": "Requested ship month",
            "customer": "Customer",
            "customer_type": "Customer type",
            "product_sku": "Product SKU",
            "product_name": "Product",
            "gross_order_units": st.column_config.NumberColumn(
                "Gross orders", format="%d"
            ),
            "cancelled_units": st.column_config.NumberColumn(
                "Cancelled", format="%d"
            ),
            "demand_units": st.column_config.NumberColumn(
                "Internal demand", format="%d"
            ),
            "unit": "Unit",
        },
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
