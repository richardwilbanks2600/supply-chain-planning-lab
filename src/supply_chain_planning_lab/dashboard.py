"""Local Streamlit interface for validated FRED observations."""

from datetime import date
import logging
import os
from typing import cast

from dotenv import load_dotenv
import streamlit as st

from supply_chain_planning_lab.api import FredApiError
from supply_chain_planning_lab.cli import DEFAULT_START_DATE, SERIES_ID
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
        "Retrieve and inspect the FRED PERMIT construction-market indicator "
        "through the project's shared validation workflow."
    )
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
        "Latest monthly change",
        _latest_change_label(records),
        help="Latest value minus the preceding monthly observation.",
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

    if len(records) < 2:
        return "Not available"
    change = records[-1]["value"] - records[-2]["value"]
    return f"{change:+,.1f}"


if __name__ == "__main__":
    main()
