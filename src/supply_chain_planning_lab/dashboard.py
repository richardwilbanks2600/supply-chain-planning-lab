"""Local Streamlit interface for validated FRED observations."""

from datetime import date
import logging
import os
from typing import cast

from dotenv import load_dotenv
import streamlit as st

from supply_chain_planning_lab.api import FredApiError
from supply_chain_planning_lab.capacity import (
    DEFAULT_DOWNTIME_PERCENT,
    DEFAULT_HOURS_PER_SHIFT,
    DEFAULT_RUN_RATES,
    DEFAULT_SETUP_HOURS,
    DEFAULT_SHIFTS_PER_DAY,
    DEFAULT_WORKING_DAYS,
    WORK_CENTERS,
    CapacityPolicy,
    build_capacity_plan,
    filter_capacity_products,
    filter_work_centers,
    summarize_capacity_plan,
)
from supply_chain_planning_lab.cli import DEFAULT_START_DATE, SERIES_ID
from supply_chain_planning_lab.demand import (
    CUSTOMERS,
    DEFAULT_CUSTOMER_ALLOCATIONS,
    DEFAULT_LAG_MONTHS,
    DEFAULT_MARKET_SHARE_PERCENT,
    DEFAULT_UNITS_PER_HOME,
    PRODUCTS,
    DemandAssumptions,
    DemandDataError,
    DemandRecord,
    filter_demand,
    generate_demand,
    load_fred_snapshot,
    monthly_demand_comparison,
    summarize_demand,
)
from supply_chain_planning_lab.forecasting import (
    METHOD_LABELS,
    PRIMARY_METHOD,
    compare_baselines,
    filter_forecasts,
    summarize_forecasts,
)
from supply_chain_planning_lab.driver_forecasting import (
    DRIVER_METHOD_LABEL,
    MAX_FORECAST_HORIZON,
    calculate_driver_forecasts,
    filter_driver_forecasts,
    forecast_origins,
    summarize_driver_status,
    summarize_horizons,
)
from supply_chain_planning_lab.inventory import (
    DEFAULT_SAFETY_STOCK_PERCENT,
    DEFAULT_STARTING_INVENTORY,
    InventoryPolicy,
    build_inventory_plan,
    filter_inventory_plan,
    summarize_inventory_plan,
)
from supply_chain_planning_lab.learning import (
    FORECAST_METHOD_LESSONS,
    TEXTBOOK_NAME,
    TEXTBOOK_VERSION,
    help_text,
    learning_sections,
    learning_term,
    search_learning_terms,
)
from supply_chain_planning_lab.integrated_planning import (
    IntegratedPlan,
    build_integrated_plan,
    records_csv,
)
from supply_chain_planning_lab.materials import (
    BOM,
    COMPONENTS,
    DEFAULT_MATERIAL_INVENTORY,
)
from supply_chain_planning_lab.planning_workflow import (
    ProcurementInputs,
    prepare_procurement_inputs,
)
from supply_chain_planning_lab.procurement import (
    RECEIPT_TREATMENTS,
    SAFETY_STOCK_METHODS,
    SERVICE_LEVEL_Z,
    ProcurementPolicy,
    build_procurement_plan,
    compare_safety_stock,
    filter_procurement_plan,
    summarize_procurement_plan,
)
from supply_chain_planning_lab.scenario import (
    PlanningScenario,
    default_planning_scenario,
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
        "Learn how one market signal becomes expected and realized demand, then "
        "flows into inventory, purchasing, and a capacity-feasible production plan. "
        "No prior planning knowledge is assumed."
    )
    try:
        fred_records = load_fred_snapshot()
        scenario = _render_shared_scenario_controls()
        working_plan = build_integrated_plan(fred_records, scenario)
        baseline_plan = build_integrated_plan(
            fred_records,
            default_planning_scenario(forecast_origin=scenario.forecast_origin),
        )
    except (OSError, UnicodeError, ValueError) as exc:
        logger.error("Integrated dashboard scenario could not be calculated: %s", exc)
        st.error(f"The planning scenario could not be calculated: {exc}")
        return

    (
        overview_tab,
        demand_tab,
        forecast_tab,
        inventory_tab,
        procurement_tab,
        capacity_tab,
        learning_tab,
        external_tab,
    ) = st.tabs(
        (
            "Overview",
            "Demand signal",
            "Forecast",
            "Inventory",
            "Materials and procurement",
            "Capacity",
            "Learning Guide",
            "Source data",
        )
    )
    with overview_tab:
        _render_integrated_overview(working_plan, baseline_plan)
    with demand_tab:
        _render_integrated_demand(fred_records, working_plan)
    with forecast_tab:
        _render_integrated_forecast(fred_records, working_plan)
    with inventory_tab:
        _render_integrated_inventory(working_plan)
    with procurement_tab:
        _render_integrated_procurement(working_plan)
    with capacity_tab:
        _render_integrated_capacity(working_plan)
    with learning_tab:
        _render_learning_guide()
    with external_tab:
        _render_external_indicator()


def _render_term_popover(label: str, keys: tuple[str, ...]) -> None:
    """Show focused definitions without interrupting the learner's workflow."""

    with st.popover(label):
        for key in keys:
            item = learning_term(key)
            st.markdown(f"**{item.term}**")
            st.write(item.short)
            if item.formula:
                st.code(item.formula, language=None)
        st.caption("Search the Learning Guide for examples and common mistakes.")


def _render_learning_guide() -> None:
    """Render the searchable glossary, forecast lessons, and further study."""

    st.header("Learning Guide: planning terms in plain language")
    st.write(
        "Use this page whenever a dashboard word, unit, formula, or assumption is "
        "unfamiliar. Search by a term such as `bias`, `safety stock`, `OTIF`, "
        "`hours`, or `backlog`."
    )
    st.info(
        "Guidance is layered: question-mark help gives a one-sentence definition, "
        "What does this mean? panels show nearby formulas, and this guide keeps "
        "the full explanation, example, and interpretation warning together."
    )
    search, category = st.columns((2, 1))
    query = search.text_input(
        "Search the Learning Guide",
        key="learning_guide_search",
        help="Searches terms, definitions, formulas, examples, and related words.",
    )
    section_choice = category.selectbox(
        "Limit results to a topic",
        ("All topics", *learning_sections()),
        key="learning_guide_section",
    )
    matches = search_learning_terms(
        query,
        section=None if section_choice == "All topics" else section_choice,
    )
    result_word = "definition" if len(matches) == 1 else "definitions"
    st.caption(f"Showing {len(matches)} {result_word}.")
    if not matches:
        st.warning(
            "No definition matches that search. Try a shorter word or choose "
            "All topics."
        )
    for item in matches:
        with st.expander(f"{item.term} - {item.short}"):
            st.write(item.detail)
            st.caption(f"Dashboard location: {item.dashboard_tab}")
            if item.formula:
                st.markdown("**Formula or rule**")
                st.code(item.formula, language=None)
            if item.example:
                st.markdown("**Small example**")
                st.write(item.example)
            if item.common_mistake:
                st.markdown("**Common interpretation mistake**")
                st.warning(item.common_mistake)

    st.divider()
    st.subheader("Rolling averages: responsiveness versus smoothing")
    st.write(
        "A forecast can react quickly to new information or smooth short-lived "
        "movement, but it cannot maximize both at the same time. Window length, "
        "weights, and alpha decide where a method sits on that trade-off."
    )
    st.caption(
        "Alpha is a value from 0 to 1 that controls how strongly simple "
        "exponential smoothing reacts to the newest information."
    )
    st.dataframe(
        [
            {
                "method": item.name,
                "formula": item.formula,
                "responsiveness": item.responsiveness,
                "smoothing": item.smoothing,
                "learning use": item.best_teaching_use,
                "caution": item.caution,
            }
            for item in FORECAST_METHOD_LESSONS
        ],
        hide_index=True,
        width="stretch",
    )
    with st.expander("Walk through a changing-demand example"):
        st.write(
            "Suppose monthly demand is 20, 20, 20, and then 40 units. A short "
            "average begins rising sooner because the new 40 is a large part of "
            "its window. A longer average changes less because more older 20s "
            "remain in the calculation. That stability is smoothing; the slower "
            "reaction is lag."
        )
        st.write(
            "The dashboard currently calculates a 3-month simple average as an "
            "explainable baseline. Weighted and exponential methods are described "
            "here for comparison, not presented as implemented forecast results."
        )

    st.divider()
    st.subheader("Further study")
    st.write(f"**{TEXTBOOK_NAME}, {TEXTBOOK_VERSION}**")
    st.caption(
        "This project is a guided introduction. The textbook provides deeper "
        "coverage of forecasting, inventory, materials, and capacity planning."
    )

    st.divider()
    st.subheader("Accessibility and interpretation checklist")
    st.markdown(
        "- Every input has a visible label; help is not conveyed by an icon alone.\n"
        "- Exception metrics use words and counts, not color alone.\n"
        "- Charts are followed by tables containing the same planning records.\n"
        "- Units appear in metric labels, table fields, captions, or definitions.\n"
        "- Keyboard users can reach native Streamlit controls and expanders.\n"
        "- Source data, fictional assumptions, forecasts, requirements, and "
        "feasible output are named separately."
    )


def _render_shared_scenario_controls() -> PlanningScenario:
    """Collect one session-only set of assumptions for every planning layer."""

    st.sidebar.header("Your working scenario")
    st.sidebar.write(
        "Change an assumption here and every downstream page recalculates. "
        "Nothing is saved outside this browser session."
    )
    if st.sidebar.button("Reset all assumptions to defaults"):
        for key in tuple(st.session_state):
            if str(key).startswith("scenario_"):
                del st.session_state[key]
        st.rerun()

    forecast_origin = st.sidebar.selectbox(
        "Forecast starting point",
        forecast_origins(),
        index=len(forecast_origins()) - 1,
        key="scenario_forecast_origin",
        help=help_text("forecast_origin"),
    )

    with st.sidebar.expander("1. Demand assumptions", expanded=True):
        market_share_percent = st.slider(
            "Company market share (%)",
            min_value=0.01,
            max_value=1.00,
            value=DEFAULT_MARKET_SHARE_PERCENT,
            step=0.01,
            format="%.2f%%",
            key="scenario_market_share",
            help=help_text("market_share"),
        )
        allocation_cuts = st.slider(
            "Customer allocation split points (%)",
            min_value=0,
            max_value=100,
            value=(50, 80),
            step=1,
            key="scenario_customer_allocations",
            help=(
                f"{help_text('customer_allocation')} The first point sets Building "
                "Houses Company. The distance between the points sets Building "
                "Supply Company. The remainder sets Building Remodeler."
            ),
        )
        first_cut, second_cut = allocation_cuts
        customer_allocations = {
            "Building Houses Company": first_cut / 100,
            "Building Supply Company": (second_cut - first_cut) / 100,
            "Building Remodeler": (100 - second_cut) / 100,
        }
        st.caption(
            f"Resulting allocation — Building Houses Company: {first_cut}% | "
            f"Building Supply Company: {second_cut - first_cut}% | "
            f"Building Remodeler: {100 - second_cut}%"
        )
        units_per_home = {
            product_sku: float(
                st.number_input(
                    f"{PRODUCTS[product_sku]} ({product_sku}) units per home",
                    min_value=0.0,
                    value=DEFAULT_UNITS_PER_HOME[product_sku],
                    step=1.0,
                    key=f"scenario_units_{product_sku}",
                    help=f"{help_text('units_per_home')} Product: {PRODUCTS[product_sku]}.",
                )
            )
            for product_sku in PRODUCTS
        }

    with st.sidebar.expander("2. Finished-goods inventory"):
        finished_safety_percent = st.slider(
            "Finished-goods safety stock (%)",
            min_value=0,
            max_value=100,
            value=int(DEFAULT_SAFETY_STOCK_PERCENT),
            step=5,
            key="scenario_finished_safety",
            help=help_text("safety_stock"),
        )
        finished_inventory = {
            product_sku: int(
                st.number_input(
                    f"Starting finished units — {PRODUCTS[product_sku]} ({product_sku})",
                    min_value=0,
                    value=DEFAULT_STARTING_INVENTORY[product_sku],
                    step=10,
                    key=f"scenario_finished_inventory_{product_sku}",
                    help=help_text("sku"),
                )
            )
            for product_sku in PRODUCTS
        }

    with st.sidebar.expander("3. Materials and supplier risk"):
        material_method = st.selectbox(
            "Material safety-stock method",
            SAFETY_STOCK_METHODS,
            index=SAFETY_STOCK_METHODS.index("percentage"),
            key="scenario_material_method",
            format_func=lambda value: {
                "none": "No extra material",
                "percentage": "Percentage of next month's need",
                "statistical": "Demand and supplier variability",
            }[value],
            help=help_text("material_safety_stock"),
        )
        material_percentage = st.slider(
            "Material safety stock (%)",
            min_value=0,
            max_value=100,
            value=25,
            step=5,
            key="scenario_material_percentage",
            help=help_text("percentage_material_safety_stock"),
            disabled=material_method != "percentage",
        )
        service_level = st.selectbox(
            "Target material service level",
            tuple(SERVICE_LEVEL_Z),
            index=1,
            key="scenario_service_level",
            format_func=lambda value: f"{value:g}%",
            help=help_text("service_level"),
            disabled=material_method != "statistical",
        )
        if material_method == "none":
            st.caption(
                "No material safety-stock input is active. The percentage and "
                "service-level settings do not affect this scenario."
            )
        elif material_method == "percentage":
            st.caption(
                "The percentage input is active. Target service level applies "
                "only to the statistical method."
            )
        else:
            st.caption(
                "Target service level is active. The percentage input applies "
                "only to the percentage method."
            )
        receipt_treatment = st.selectbox(
            "How should open supplier orders be counted?",
            RECEIPT_TREATMENTS,
            key="scenario_receipt_treatment",
            format_func=lambda value: {
                "full": "Count the full scheduled quantity",
                "risk_adjusted": "Reduce it using supplier OTIF history",
            }[value],
            help=help_text("risk_adjusted_receipt"),
        )
        material_inventory = {
            component_sku: int(
                st.number_input(
                    f"Starting material — {component.name} ({component_sku})",
                    min_value=0,
                    value=DEFAULT_MATERIAL_INVENTORY[component_sku],
                    step=50,
                    key=f"scenario_material_inventory_{component_sku}",
                    help=f"{component.name}, measured in {component.unit}.",
                )
            )
            for component_sku, component in COMPONENTS.items()
        }

    with st.sidebar.expander("4. Production capacity"):
        working_days = st.slider(
            "Working days per month",
            1,
            31,
            DEFAULT_WORKING_DAYS,
            key="scenario_working_days",
            help=help_text("regular_capacity"),
        )
        shifts_per_day = st.slider(
            "Shifts per day",
            1,
            3,
            DEFAULT_SHIFTS_PER_DAY,
            key="scenario_shifts",
            help=help_text("regular_capacity"),
        )
        hours_per_shift = st.slider(
            "Hours per shift",
            4.0,
            12.0,
            DEFAULT_HOURS_PER_SHIFT,
            0.5,
            key="scenario_shift_hours",
            help=help_text("regular_capacity"),
        )
        downtime_percent = st.slider(
            "Planned downtime (%)",
            0,
            50,
            int(DEFAULT_DOWNTIME_PERCENT),
            5,
            key="scenario_downtime",
            help=help_text("planned_downtime"),
        )
        setup_hours = st.slider(
            "Setup hours per active product",
            0.0,
            16.0,
            DEFAULT_SETUP_HOURS,
            1.0,
            key="scenario_setup_hours",
            help=help_text("setup_time"),
        )
        overtime_hours = {
            work_center_id: float(
                st.slider(
                    f"{work_center_name} overtime hours",
                    0,
                    40,
                    0,
                    4,
                    key=f"scenario_overtime_{work_center_id}",
                    help=help_text("effective_capacity"),
                )
            )
            for work_center_id, work_center_name in WORK_CENTERS.items()
        }
        run_rates = {
            product_sku: float(
                st.number_input(
                    f"{product_sku} units produced per hour",
                    min_value=0.1,
                    value=DEFAULT_RUN_RATES[product_sku],
                    step=0.5,
                    key=f"scenario_run_rate_{product_sku}",
                    help=help_text("run_rate"),
                )
            )
            for product_sku in PRODUCTS
        }

    return PlanningScenario(
        forecast_origin=forecast_origin,
        demand=DemandAssumptions(
            market_share_percent=market_share_percent,
            customer_allocations=customer_allocations,
            units_per_home=units_per_home,
        ),
        finished_goods=InventoryPolicy(
            starting_inventory=finished_inventory,
            safety_stock_percent=float(finished_safety_percent),
        ),
        procurement=ProcurementPolicy(
            starting_inventory=material_inventory,
            safety_stock_method=material_method,
            percentage=float(material_percentage),
            service_level=service_level,
            receipt_treatment=receipt_treatment,
        ),
        capacity=CapacityPolicy(
            working_days_per_month=working_days,
            shifts_per_day=shifts_per_day,
            hours_per_shift=hours_per_shift,
            planned_downtime_percent=float(downtime_percent),
            setup_hours_per_active_product=setup_hours,
            overtime_hours=overtime_hours,
            run_rates=run_rates,
        ),
    )


def _render_integrated_overview(
    working: IntegratedPlan,
    baseline: IntegratedPlan,
) -> None:
    """Introduce the planning story, comparisons, exceptions, and downloads."""

    st.header("Start here: follow one planning story")
    st.write(
        "The dashboard starts with a national building-permit signal, calculates "
        "expected demand, applies fixed company variation to realized demand, "
        "decides what should be made and purchased, and checks factory capacity."
    )
    _render_term_popover(
        "What do these planning stages mean?",
        (
            "market_signal",
            "demand_realization_factor",
            "baseline_scenario",
            "net_production_requirement",
            "bom",
            "capacity_feasible_production",
        ),
    )
    st.info(
        "Use the controls on the left to create a working scenario. The baseline "
        "uses the approved defaults at the same forecast starting point, so the "
        "comparison isolates your changes."
    )
    st.subheader("How the pieces connect")
    st.markdown(
        "1. **Demand signal:** building permits provide an external market pace.\n"
        "2. **Demand realization:** fixed factors move company demand around expectation.\n"
        "3. **Forecast:** future realized demand must be estimated.\n"
        "4. **Inventory:** stock on hand reduces what must be produced.\n"
        "5. **Materials:** the bill of materials determines what must be purchased.\n"
        "6. **Capacity:** available work-center hours limit what can be built."
    )

    comparison_rows = _summary_comparison_rows(working, baseline)
    st.subheader("Baseline compared with your working scenario")
    st.dataframe(
        comparison_rows,
        hide_index=True,
        width="stretch",
        column_config={
            "measure": "Planning measure",
            "baseline": "Baseline",
            "working": "Working scenario",
            "difference": st.column_config.NumberColumn(
                "Difference", format="%+d"
            ),
            "meaning": "Why it matters",
        },
    )

    st.subheader("What needs attention?")
    past_due = [
        row
        for row in working.procurement_records
        if row["release_status"] == "past_due"
        and row["net_purchase_receipt_units"] > 0
    ]
    at_risk = [
        row
        for row in working.procurement_records
        if row["receipt_at_risk_units"] > 0
    ]
    overloaded = [
        row for row in working.capacity_plan.work_centers if row["overloaded"]
    ]
    exception_columns = st.columns(4)
    exception_columns[0].metric(
        "Past-due purchase releases",
        len(past_due),
        help=help_text("past_due_release"),
    )
    exception_columns[1].metric(
        "Supplier receipts at risk",
        len(at_risk),
        help=help_text("risk_adjusted_receipt"),
    )
    exception_columns[2].metric(
        "Overloaded work-center months",
        len(overloaded),
        help=help_text("overload"),
    )
    exception_columns[3].metric(
        "Ending deferred production",
        f"{working.summary.ending_deferred_production_units:,}",
        help=help_text("deferred_production"),
    )
    with st.expander("Inspect purchasing exceptions"):
        if past_due or at_risk:
            st.dataframe(
                past_due + [row for row in at_risk if row not in past_due],
                hide_index=True,
                width="stretch",
            )
        else:
            st.success("No purchasing exceptions appear in this scenario.")
    with st.expander("Inspect overloaded work centers"):
        if overloaded:
            st.dataframe(overloaded, hide_index=True, width="stretch")
        else:
            st.success("The requested production fits within effective capacity.")

    final_deferred = {}
    for row in working.capacity_plan.products:
        final_deferred[row["product_sku"]] = row["ending_deferred_units"]
    st.subheader("Unconstrained requirement versus feasible output")
    st.write(
        "The requirement says what should be produced. The feasible plan says what "
        "the work centers can build. Their remaining difference is deferred; it is "
        "not silently removed from the plan."
    )
    requirement, feasible, deferred = st.columns(3)
    requirement.metric(
        "Unconstrained production requirement",
        f"{working.summary.net_production_requirement_units:,}",
        help=help_text("net_production_requirement"),
    )
    feasible.metric(
        "Capacity-feasible production",
        f"{sum(row['planned_production_units'] for row in working.capacity_plan.products):,}",
        help=help_text("capacity_feasible_production"),
    )
    deferred.metric(
        "Deferred at end of horizon",
        f"{sum(final_deferred.values()):,}",
        help=help_text("deferred_production"),
    )

    st.subheader("Where each result comes from")
    st.dataframe(
        [
            {
                "step": "Demand signal",
                "main input": "Fixed FRED history and realization factors",
                "result": "Expected and realized fictional product demand",
            },
            {
                "step": "Inventory",
                "main input": "Forecast demand and finished-goods stock",
                "result": "Net production requirement",
            },
            {
                "step": "Materials",
                "main input": "Production requirement and bill of materials",
                "result": "Purchase receipts and release timing",
            },
            {
                "step": "Capacity",
                "main input": "Production requirement and available hours",
                "result": "Feasible production and deferred units",
            },
        ],
        hide_index=True,
        width="stretch",
    )

    st.subheader("Download your working scenario")
    downloads = st.columns(5)
    downloads[0].download_button(
        "Demand CSV",
        records_csv(working.demand_records),
        "working-demand.csv",
        "text/csv",
    )
    downloads[1].download_button(
        "Inventory CSV",
        records_csv(working.inventory_records),
        "working-inventory.csv",
        "text/csv",
    )
    downloads[2].download_button(
        "Materials CSV",
        records_csv(working.procurement_records),
        "working-materials.csv",
        "text/csv",
    )
    downloads[3].download_button(
        "Capacity CSV",
        records_csv(working.capacity_plan.work_centers),
        "working-capacity-centers.csv",
        "text/csv",
    )
    downloads[4].download_button(
        "Production CSV",
        records_csv(working.capacity_plan.products),
        "working-capacity-products.csv",
        "text/csv",
    )


def _summary_comparison_rows(
    working: IntegratedPlan,
    baseline: IntegratedPlan,
) -> list[dict[str, str | int]]:
    """Build learner-friendly baseline comparison rows."""

    measures = (
        (
            "12-month forecast demand",
            "forecast_demand_units",
            "Expected finished-product demand across the plan horizon.",
        ),
        (
            "Net production requirement",
            "net_production_requirement_units",
            "Units requested after finished-goods inventory and safety stock.",
        ),
        (
            "Material purchase actions",
            "material_purchase_actions",
            "Component-months that require a planned purchase receipt.",
        ),
        (
            "Past-due order releases",
            "past_due_release_actions",
            "Purchases whose recommended release month is before the plan origin.",
        ),
        (
            "Overloaded work-center months",
            "overloaded_work_center_months",
            "Months where requested setup and runtime exceed effective hours.",
        ),
        (
            "Ending deferred production",
            "ending_deferred_production_units",
            "Requested units still unbuilt at the end of the horizon.",
        ),
    )
    rows = []
    for label, field, meaning in measures:
        baseline_value = getattr(baseline.summary, field)
        working_value = getattr(working.summary, field)
        rows.append(
            {
                "measure": label,
                "baseline": baseline_value,
                "working": working_value,
                "difference": working_value - baseline_value,
                "meaning": meaning,
            }
        )
    return rows


def _render_integrated_demand(
    fred_records: list[ProcessedObservation],
    plan: IntegratedPlan,
) -> None:
    """Explain the external signal and its fictional internal translation."""

    st.header("1. Where does company demand come from?")
    st.write(
        "Federal Reserve Economic Data (FRED) building permits are an external "
        "market signal, not customer orders. The project first calculates "
        "FRED-driven expected demand, then applies committed static factors to "
        "create fictional realized company demand."
    )
    _render_term_popover(
        "What does this demand calculation mean?",
        (
            "fred_permit",
            "saar",
            "demand_lag",
            "market_share",
            "units_per_home",
            "customer_allocation",
            "fred_expected_demand",
            "demand_realization_factor",
            "internal_demand",
        ),
    )
    assumptions = plan.scenario.demand
    st.dataframe(
        [
            {
                "assumption": "Company market share",
                "working value": f"{assumptions.market_share_percent:.2f}%",
                "purpose": "Narrows the national market to the fictional company.",
            },
            {
                "assumption": "Demand lag",
                "working value": f"{DEFAULT_LAG_MONTHS} months",
                "purpose": "Moves a permit signal to a later requested ship month.",
            },
            {
                "assumption": "Static demand variation",
                "working value": "Usually within ±15%; unusual months up to ±25%",
                "purpose": "Keeps FRED central without making it equal company demand.",
            },
            {
                "assumption": "Cancellations",
                "working value": "None",
                "purpose": "Keeps the generated teaching demand repeatable.",
            },
        ],
        hide_index=True,
        width="stretch",
    )
    customer_choice = st.selectbox(
        "Customer to explore",
        ("All customers", *CUSTOMERS),
    )
    product_choice = st.selectbox(
        "Product to explore in demand",
        ("All products", *PRODUCTS),
        format_func=lambda value: (
            value if value == "All products" else f"{value} - {PRODUCTS[value]}"
        ),
    )
    selected = filter_demand(
        plan.demand_records,
        customer=None if customer_choice == "All customers" else customer_choice,
        product_sku=None if product_choice == "All products" else product_choice,
    )
    summary = summarize_demand(selected)
    comparison = monthly_demand_comparison(selected)
    monthly_gap_percentages = [
        abs(row["realized_demand_units"] - row["fred_expected_demand_units"])
        / row["fred_expected_demand_units"]
        * 100
        for row in comparison
        if row["fred_expected_demand_units"]
    ]
    average_monthly_gap = (
        sum(monthly_gap_percentages) / len(monthly_gap_percentages)
        if monthly_gap_percentages
        else 0.0
    )
    source, periods, expected, demand, gap = st.columns(5)
    source.metric("Months in the FRED source", len(fred_records))
    periods.metric("Demand months displayed", len({row["period"] for row in selected}))
    expected.metric(
        "FRED-driven expected units",
        f"{summary.fred_expected_demand_units:,}",
        help=help_text("fred_expected_demand"),
    )
    demand.metric(
        "Realized fictional demand units",
        f"{summary.demand_units:,}",
        help=help_text("internal_demand"),
    )
    gap.metric(
        "Average absolute monthly gap",
        f"{average_monthly_gap:.1f}%",
        help=(
            "Average monthly percentage distance between FRED-driven expectation "
            "and realized fictional demand for the selected records."
        ),
    )
    st.subheader("External permit pace")
    st.line_chart(
        [
            {"period": record["period"], "permit_saar": record["value"]}
            for record in fred_records
        ],
        x="period",
        y="permit_saar",
    )
    st.caption(
        "SAAR means seasonally adjusted annual rate. It is an annualized pace, "
        "not the number of permits issued during that single month."
    )
    st.subheader("FRED-driven expectation versus realized company demand")
    st.line_chart(
        comparison,
        x="period",
        y=("fred_expected_demand_units", "realized_demand_units"),
    )
    st.caption(
        "The gap comes from the committed static product-month factors. It is "
        "repeatable and does not change when the dashboard reruns. Above- and "
        "below-expectation months can offset each other in the total, so the "
        "average absolute monthly gap shows their typical distance."
    )
    with st.expander("Inspect demand calculation records"):
        st.dataframe(
            selected,
            hide_index=True,
            width="stretch",
            column_config={
                "fred_expected_demand_units": "FRED-driven expected units",
                "realization_factor": st.column_config.NumberColumn(
                    "Realization factor", format="%.4f"
                ),
                "demand_units": "Realized demand units",
            },
        )


def _render_integrated_forecast(
    fred_records: list[ProcessedObservation],
    plan: IntegratedPlan,
) -> None:
    """Teach internal-history baselines and unknown external drivers together."""

    st.header("2. What do we think will happen next?")
    st.write(
        "A forecast is an estimate made before realized demand is known. Start "
        "with simple methods so every result has a clear comparison point."
    )
    _render_term_popover(
        "What does forecast performance mean?",
        (
            "forecast_origin",
            "forecast_horizon",
            "rolling_origin",
            "known_driver",
            "forecasted_driver",
            "generated_backtest_actual",
            "mae",
            "bias",
        ),
    )
    _render_forecast_baselines(plan.demand_records)
    st.divider()
    _render_fred_informed_forecast(
        fred_records,
        plan.demand_records,
        plan.scenario.demand,
    )


def _render_integrated_inventory(plan: IntegratedPlan) -> None:
    """Explain how forecast demand and finished stock become production needs."""

    st.header("3. How much finished product should we make?")
    st.write(
        "The inventory plan begins with forecast demand, subtracts finished goods "
        "already available, and adds the selected safety-stock protection."
    )
    _render_term_popover(
        "What does the inventory calculation mean?",
        (
            "inventory_position",
            "safety_stock",
            "net_production_requirement",
            "projected_ending_inventory",
        ),
    )
    st.caption(
        f"Working policy: {plan.scenario.finished_goods.safety_stock_percent:g}% "
        "of the following month's forecast. Scheduled finished-goods receipts are zero."
    )
    summary = summarize_inventory_plan(plan.inventory_records)
    demand, production, ending = st.columns(3)
    demand.metric("12-month forecast demand", f"{summary.forecast_demand_units:,}")
    production.metric(
        "Unconstrained production requirement",
        f"{summary.net_production_requirement_units:,}",
        help=help_text("net_production_requirement"),
    )
    ending.metric(
        "Final projected finished inventory",
        f"{summary.final_projected_inventory_units:,}",
    )
    product_sku = st.selectbox(
        "Finished product to explore",
        tuple(PRODUCTS),
        format_func=lambda value: f"{value} - {PRODUCTS[value]}",
    )
    selected = filter_inventory_plan(plan.inventory_records, product_sku=product_sku)
    st.line_chart(
        [
            {
                "period": row["period"],
                "forecast_demand": row["forecast_demand_units"],
                "production_requirement": row[
                    "net_production_requirement_units"
                ],
                "projected_ending_inventory": row[
                    "projected_ending_inventory_units"
                ],
            }
            for row in selected
        ],
        x="period",
        y=(
            "forecast_demand",
            "production_requirement",
            "projected_ending_inventory",
        ),
    )
    st.dataframe(selected, hide_index=True, width="stretch")
    example = selected[0]
    with st.expander("Show the first month's inventory calculation"):
        st.write(
            f"{example['forecast_demand_units']} forecast units + "
            f"{example['safety_stock_target_units']} safety-stock units - "
            f"{example['inventory_position_units']} available units = "
            f"{example['net_production_requirement_units']} units to produce."
        )


def _render_integrated_procurement(plan: IntegratedPlan) -> None:
    """Explain BOM requirements, suppliers, and purchase-release timing."""

    st.header("4. What materials should we purchase, and when?")
    st.write(
        "The bill of materials translates finished-product production into glass, "
        "vinyl, slabs, frames, and hardware. Inventory and open supplier orders "
        "reduce what still needs to be purchased."
    )
    _render_term_popover(
        "What does the purchasing calculation mean?",
        (
            "bom",
            "gross_material_requirement",
            "scheduled_receipt",
            "otif",
            "material_safety_stock",
            "statistical_safety_stock",
            "service_level",
            "purchase_receipt",
            "order_release",
        ),
    )
    with st.expander("Start with the bill of materials"):
        st.dataframe(
            [
                {
                    "finished product": product_sku,
                    "component": COMPONENTS[component_sku].name,
                    "quantity per product": quantity,
                    "unit": COMPONENTS[component_sku].unit,
                }
                for product_sku, entries in BOM.items()
                for component_sku, quantity in entries
            ],
            hide_index=True,
            width="stretch",
        )
    summary = summarize_procurement_plan(plan.procurement_records)
    actions, past_due, risk = st.columns(3)
    actions.metric(
        "Material purchase actions",
        summary.purchase_action_count,
        help=help_text("purchase_receipt"),
    )
    past_due.metric(
        "Past-due order releases",
        summary.past_due_action_count,
        help=help_text("past_due_release"),
    )
    risk.metric(
        "Supplier receipts reduced for risk",
        summary.receipt_at_risk_count,
        help=help_text("risk_adjusted_receipt"),
    )

    st.subheader("How reliably have the fictional suppliers delivered?")
    st.caption(
        "On-time-in-full (OTIF) means a delivery arrived by its promise date and "
        "included the complete ordered quantity."
    )
    st.dataframe(
        [
            {
                "component": item.component_sku,
                "supplier": item.supplier_name,
                "deliveries": item.delivery_count,
                "average lead months": item.average_actual_lead_months,
                "on-time rate": item.on_time_rate,
                "fill rate": item.fill_rate,
                "OTIF rate": item.otif_rate,
            }
            for item in plan.procurement_inputs.supplier_performance
        ],
        hide_index=True,
        width="stretch",
    )
    comparisons = compare_safety_stock(
        plan.procurement_inputs.material_requirements,
        plan.procurement_inputs.material_error_stats,
        plan.procurement_inputs.supplier_performance,
        percentage=plan.scenario.procurement.percentage,
        service_level=plan.scenario.procurement.service_level,
    )
    with st.expander("Compare material safety-stock methods"):
        st.dataframe(
            [
                {
                    "component": item.component_sku,
                    "none": item.none_target_units,
                    "percentage": item.percentage_target_units,
                    "statistical": item.statistical_target_units,
                }
                for item in comparisons
            ],
            hide_index=True,
            width="stretch",
        )

    component_sku = st.selectbox(
        "Purchased component to explore",
        tuple(COMPONENTS),
        format_func=lambda value: f"{value} - {COMPONENTS[value].name}",
    )
    selected = filter_procurement_plan(
        plan.procurement_records,
        component_sku=component_sku,
    )
    st.line_chart(
        [
            {
                "period": row["period"],
                "gross_material_need": row["gross_requirement_units"],
                "planned_purchase_receipt": row["net_purchase_receipt_units"],
                "projected_ending_material": row[
                    "projected_ending_inventory_units"
                ],
            }
            for row in selected
        ],
        x="period",
        y=(
            "gross_material_need",
            "planned_purchase_receipt",
            "projected_ending_material",
        ),
    )
    st.dataframe(selected, hide_index=True, width="stretch")


def _render_integrated_capacity(plan: IntegratedPlan) -> None:
    """Explain capacity feasibility and deferred production without jargon."""

    st.header("5. What can the factory actually build?")
    st.write(
        "A production requirement is a request. Capacity checks whether the "
        "available work-center hours can satisfy it. Units that do not fit are "
        "carried forward as deferred production."
    )
    _render_term_popover(
        "What does the capacity calculation mean?",
        (
            "work_center",
            "effective_capacity",
            "setup_time",
            "run_rate",
            "required_utilization",
            "overload",
            "capacity_factor",
            "deferred_production",
        ),
    )
    summary = summarize_capacity_plan(plan.capacity_plan)
    overloads, deferred, maximum = st.columns(3)
    overloads.metric(
        "Overloaded work-center months",
        summary.overloaded_work_center_months,
        help=help_text("overload"),
    )
    deferred.metric(
        "Production still deferred at the end",
        f"{summary.ending_deferred_units:,}",
        help=help_text("deferred_production"),
    )
    maximum.metric(
        "Highest required utilization",
        f"{summary.maximum_required_utilization_percent:.1f}%",
        help=help_text("required_utilization"),
    )
    work_center_id = st.selectbox(
        "Work center to explore",
        tuple(WORK_CENTERS),
        format_func=lambda value: WORK_CENTERS[value],
    )
    centers = filter_work_centers(
        plan.capacity_plan.work_centers,
        work_center_id=work_center_id,
    )
    st.subheader("Hours requested compared with hours available")
    st.line_chart(
        [
            {
                "period": row["period"],
                "hours_requested": row["required_hours"],
                "hours_available": row["effective_capacity_hours"],
            }
            for row in centers
        ],
        x="period",
        y=("hours_requested", "hours_available"),
    )
    st.dataframe(centers, hide_index=True, width="stretch")
    eligible = tuple(
        product_sku
        for product_sku in PRODUCTS
        if any(
            row["product_sku"] == product_sku
            and row["work_center_id"] == work_center_id
            for row in plan.capacity_plan.products
        )
    )
    product_sku = st.selectbox(
        "Capacity-constrained product to explore",
        eligible,
        format_func=lambda value: f"{value} - {PRODUCTS[value]}",
    )
    products = filter_capacity_products(
        plan.capacity_plan.products,
        product_sku=product_sku,
    )
    st.subheader("Units requested, built, and deferred")
    st.line_chart(
        [
            {
                "period": row["period"],
                "units_requested": row["total_requested_units"],
                "units_planned": row["planned_production_units"],
                "units_deferred": row["ending_deferred_units"],
            }
            for row in products
        ],
        x="period",
        y=("units_requested", "units_planned", "units_deferred"),
    )
    st.dataframe(products, hide_index=True, width="stretch")
    st.warning(
        "This capacity-feasible view does not silently rewrite the earlier inventory "
        "or purchasing requirements. Keeping both views visible helps you see the "
        "trade-off instead of hiding it."
    )


def _render_internal_demand() -> tuple[
    list[ProcessedObservation], list[DemandRecord], DemandAssumptions
] | None:
    """Render a repeatable scenario from fixed FRED and realization inputs."""

    st.header("FRED-anchored expected and realized demand")
    st.write(
        "The source is a fixed FRED PERMIT snapshot covering 2000 through 2025. "
        "Sliders change visible business assumptions; committed variation factors "
        "stay fixed and no random values are generated at runtime."
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
        "Customer allocation split points (%)",
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
        "Demand product",
        ("All products", *PRODUCTS),
        format_func=lambda value: (
            value if value == "All products" else f"{value} - {PRODUCTS[value]}"
        ),
    )
    selected = filter_demand(
        records,
        customer=None if customer_choice == "All customers" else customer_choice,
        product_sku=None if product_choice == "All products" else product_choice,
    )
    summary = summarize_demand(selected)

    source, months, expected, demand = st.columns(4)
    source.metric("FRED source months", len(fred_records))
    months.metric("Derived demand months", len({row["period"] for row in selected}))
    expected.metric(
        "FRED-driven expected units", f"{summary.fred_expected_demand_units:,}"
    )
    demand.metric("Realized fictional demand units", f"{summary.demand_units:,}")

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

    st.subheader("Expected versus realized monthly demand")
    st.line_chart(
        monthly_demand_comparison(selected),
        x="period",
        y=("fred_expected_demand_units", "realized_demand_units"),
    )

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
            "fred_expected_demand_units": st.column_config.NumberColumn(
                "FRED-driven expected demand", format="%d"
            ),
            "realization_factor": st.column_config.NumberColumn(
                "Realization factor", format="%.4f"
            ),
            "demand_units": st.column_config.NumberColumn(
                "Realized fictional demand", format="%d"
            ),
            "unit": "Unit",
        },
    )
    return fred_records, records, assumptions


def _render_forecast_baselines(demand_records: list[DemandRecord]) -> None:
    """Compare approved baseline forecasts for the current demand scenario."""

    st.header("Baseline forecast comparison")
    st.write(
        "Each method forecasts monthly product demand using only earlier internal "
        "demand. The common evaluation period is January 2020 through December 2025."
    )
    st.caption(
        "Error = realized demand - forecast. Positive error means demand was underforecast; "
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

    st.subheader("Realized fictional demand versus forecast")
    st.caption(
        "Realized demand includes the committed static product-month variation "
        "and is treated as the known outcome for this historical backtest."
    )
    st.line_chart(
        [
            {
                "period": record["period"],
                "realized_demand_units": record["actual_units"],
                "forecast_units": record["forecast_units"],
            }
            for record in selected
        ],
        x="period",
        y=("realized_demand_units", "forecast_units"),
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
            "actual_units": "Realized fictional demand units",
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
            "forecast(t) = [realized(t-1) + realized(t-2) + realized(t-3)] / 3",
            language="text",
        )
        st.write(
            "A three-month window smooths short-term movement but can lag when "
            "demand rises or falls for several months. The Learning Guide compares "
            "other window lengths, weighted moving averages, and simple exponential "
            "smoothing."
        )


def _render_fred_informed_forecast(
    fred_records: list[ProcessedObservation],
    demand_records: list[DemandRecord],
    assumptions: DemandAssumptions,
) -> None:
    """Show how known and forecasted FRED drivers become demand forecasts."""

    st.header("FRED-informed demand forecast")
    st.write(
        "This rolling-origin backtest starts with the FRED information available "
        "at each origin, then applies the same lag and scenario assumptions used "
        "to calculate expected demand. Realized company demand also contains the "
        "static product-month variation that the forecast does not know."
    )
    st.caption(
        "Demand horizons 1-3 use already-observed lagged permit values. Horizons "
        f"4-{MAX_FORECAST_HORIZON} forecast the unknown permit driver with the "
        f"{DRIVER_METHOD_LABEL.lower()}. Both groups are scored against realized "
        "fictional demand."
    )
    records = calculate_driver_forecasts(
        fred_records,
        demand_records,
        assumptions,
    )
    known = summarize_driver_status(records, "known")
    forecasted = summarize_driver_status(records, "forecasted")

    known_count, known_mae, forecasted_count, forecasted_mae = st.columns(4)
    known_count.metric("Known-driver forecasts", known.forecast_count)
    known_mae.metric(
        "Known-driver MAE",
        f"{known.mean_absolute_error:,.1f}",
        help=(
            "The FRED driver is already known, but future company-specific demand "
            "variation is not. This error isolates that remaining difference."
        ),
    )
    forecasted_count.metric(
        "Forecasted-driver forecasts", forecasted.forecast_count
    )
    forecasted_mae.metric(
        "Forecasted-driver MAE",
        f"{forecasted.mean_absolute_error:,.1f}",
        help=(
            "Mean absolute realized-demand error when both the future FRED driver "
            "and company-specific demand variation were unknown."
        ),
    )

    st.subheader("Performance by demand horizon")
    st.dataframe(
        [
            {
                "horizon_months": summary.horizon_months,
                "driver_status": summary.driver_status,
                "forecast_count": summary.forecast_count,
                "mae": summary.mean_absolute_error,
                "bias": summary.bias,
            }
            for summary in summarize_horizons(records)
        ],
        hide_index=True,
        width="stretch",
        column_config={
            "horizon_months": "Demand horizon (months)",
            "driver_status": "FRED driver",
            "forecast_count": "Forecasts",
            "mae": st.column_config.NumberColumn("MAE", format="%.1f"),
            "bias": st.column_config.NumberColumn("Bias", format="%+.1f"),
        },
    )

    product_sku = st.selectbox(
        "FRED-informed forecast product",
        tuple(PRODUCTS),
        format_func=lambda value: f"{value} - {PRODUCTS[value]}",
    )
    horizon = st.slider(
        "FRED-informed demand horizon (months)",
        min_value=1,
        max_value=MAX_FORECAST_HORIZON,
        value=4,
        step=1,
    )
    selected = filter_driver_forecasts(
        records,
        product_sku=product_sku,
        horizon_months=horizon,
    )
    selected_summary = summarize_driver_status(
        selected, selected[0]["driver_status"]
    )
    status, mae, bias = st.columns(3)
    status.metric("Driver status", selected[0]["driver_status"].title())
    mae.metric(
        "Selected horizon MAE",
        f"{selected_summary.mean_absolute_error:,.1f}",
    )
    bias.metric("Selected horizon bias", f"{selected_summary.bias:+,.1f}")

    st.subheader("Realized fictional demand versus FRED-informed forecast")
    st.caption(
        "Realized fictional demand is the static known outcome used to score this "
        "backtest. It is not observed company demand."
    )
    st.line_chart(
        [
            {
                "demand_period": record["demand_period"],
                "realized_demand_units": record["actual_demand_units"],
                "forecast_units": record["forecast_demand_units"],
            }
            for record in selected
        ],
        x="demand_period",
        y=("realized_demand_units", "forecast_units"),
    )
    st.dataframe(
        selected,
        hide_index=True,
        width="stretch",
        column_config={
            "actual_demand_units": "Realized fictional demand units",
            "forecast_demand_units": "Forecast demand units",
        },
    )

    st.warning(
        "Teaching limitation: the evaluation uses one fixed, currently revised "
        "FRED history. It does not reproduce the vintages or publication delay "
        "that would have existed at each historical forecast origin."
    )


def _render_inventory_plan(
    fred_records: list[ProcessedObservation],
    assumptions: DemandAssumptions,
) -> tuple[str, InventoryPolicy]:
    """Turn one FRED-informed forecast into net production requirements."""

    st.header("Inventory and net production requirements")
    st.write(
        "This plan nets the FRED-informed product forecast against finished-goods "
        "inventory, then produces enough to meet demand and the safety-stock target."
    )
    st.caption(
        "Scheduled receipts are zero and production is assumed to become available "
        "in its planned month. These requirements are not yet a capacity-feasible "
        "production schedule."
    )

    origin = st.selectbox(
        "Inventory plan forecast origin",
        forecast_origins(),
        index=len(forecast_origins()) - 1,
    )
    safety_stock_percent = st.slider(
        "Safety stock (% of following-month forecast)",
        min_value=0,
        max_value=100,
        value=int(DEFAULT_SAFETY_STOCK_PERCENT),
        step=5,
    )
    st.subheader("Starting finished-goods inventory")
    starting_inventory: dict[str, int] = {}
    inventory_columns = st.columns(3)
    for column, (product_sku, product_name) in zip(
        inventory_columns, PRODUCTS.items()
    ):
        with column:
            starting_inventory[product_sku] = int(
                st.number_input(
                    f"Starting inventory — {product_sku}",
                    min_value=0,
                    value=DEFAULT_STARTING_INVENTORY[product_sku],
                    step=10,
                    help=product_name,
                )
            )

    extended_demand = generate_demand(
        fred_records,
        assumptions,
        demand_end_period="2026-01",
    )
    forecasts = calculate_driver_forecasts(
        fred_records,
        extended_demand,
        assumptions,
        origin_start=origin,
        origin_end=origin,
        max_horizon=13,
    )
    policy = InventoryPolicy(
        starting_inventory=starting_inventory,
        safety_stock_percent=float(safety_stock_percent),
    )
    records = build_inventory_plan(
        forecasts,
        policy,
        forecast_origin=origin,
    )
    summary = summarize_inventory_plan(records)
    demand, production, ending = st.columns(3)
    demand.metric("12-month forecast demand", f"{summary.forecast_demand_units:,}")
    production.metric(
        "Net production requirement",
        f"{summary.net_production_requirement_units:,}",
    )
    ending.metric(
        "Final projected inventory",
        f"{summary.final_projected_inventory_units:,}",
    )

    product_sku = st.selectbox(
        "Inventory product",
        tuple(PRODUCTS),
        format_func=lambda value: f"{value} - {PRODUCTS[value]}",
    )
    selected = filter_inventory_plan(records, product_sku=product_sku)
    st.subheader("Monthly requirements and projected inventory")
    st.line_chart(
        [
            {
                "period": record["period"],
                "forecast_demand": record["forecast_demand_units"],
                "net_production": record[
                    "net_production_requirement_units"
                ],
                "projected_ending_inventory": record[
                    "projected_ending_inventory_units"
                ],
            }
            for record in selected
        ],
        x="period",
        y=(
            "forecast_demand",
            "net_production",
            "projected_ending_inventory",
        ),
    )
    st.dataframe(
        selected,
        hide_index=True,
        width="stretch",
        column_config={
            "forecast_origin": "Forecast origin",
            "horizon_months": "Horizon",
            "period": "Plan month",
            "product_sku": "Product SKU",
            "product_name": "Product",
            "forecast_demand_units": "Forecast demand",
            "beginning_inventory_units": "Beginning inventory",
            "scheduled_receipts_units": "Scheduled receipts",
            "inventory_position_units": "Inventory position",
            "safety_stock_basis_period": "Safety basis month",
            "safety_stock_basis_units": "Following-month forecast",
            "safety_stock_percent": st.column_config.NumberColumn(
                "Safety stock (%)", format="%.1f"
            ),
            "safety_stock_target_units": "Safety-stock target",
            "net_production_requirement_units": "Net production requirement",
            "projected_ending_inventory_units": "Projected ending inventory",
        },
    )

    example = selected[0]
    with st.expander("Show the first month's calculation"):
        st.code(
            "net production = max(0, forecast demand + safety target "
            "- inventory position)",
            language="text",
        )
        st.write(
            f"For {example['period']}: max(0, "
            f"{example['forecast_demand_units']} + "
            f"{example['safety_stock_target_units']} - "
            f"{example['inventory_position_units']}) = "
            f"{example['net_production_requirement_units']} units."
        )
    st.info(
        "The percentage policy is a teaching baseline, not a statistical "
        "safety-stock recommendation. The Materials and procurement tab compares "
        "it with a statistical method after supplier variability is introduced."
    )
    return origin, policy


def _render_procurement_plan(
    fred_records: list[ProcessedObservation],
    assumptions: DemandAssumptions,
    forecast_origin: str,
    finished_goods_policy: InventoryPolicy,
) -> ProcurementInputs:
    """Render BOM, material purchasing, and supplier-risk calculations."""

    st.header("Materials, procurement, and supplier uncertainty")
    st.write(
        "The selected finished-goods production plan is exploded through the BOM, "
        "netted against raw-material inventory and open orders, and offset by each "
        "supplier's lead time."
    )
    st.caption(
        f"This view follows the Inventory plan tab's {forecast_origin} origin and "
        "finished-goods assumptions. BOM scrap is zero. Purchase recommendations "
        "are not automatically issued orders."
    )

    with st.expander("View the approved bill of materials"):
        st.dataframe(
            [
                {
                    "product_sku": product_sku,
                    "component_sku": component_sku,
                    "component": COMPONENTS[component_sku].name,
                    "quantity_per_product": quantity,
                    "unit": COMPONENTS[component_sku].unit,
                }
                for product_sku, entries in BOM.items()
                for component_sku, quantity in entries
            ],
            hide_index=True,
            width="stretch",
        )

    method = st.selectbox(
        "Material safety-stock method",
        SAFETY_STOCK_METHODS,
        index=SAFETY_STOCK_METHODS.index("percentage"),
        format_func=lambda value: {
            "none": "None",
            "percentage": "Percentage of following-month requirement",
            "statistical": "Statistical demand and lead-time variability",
        }[value],
    )
    percentage = st.slider(
        "Material safety stock (% of following-month requirement)",
        min_value=0,
        max_value=100,
        value=25,
        step=5,
    )
    service_level = st.selectbox(
        "Material service level",
        tuple(SERVICE_LEVEL_Z),
        index=1,
        format_func=lambda value: f"{value:g}% (z = {SERVICE_LEVEL_Z[value]:.3f})",
    )
    receipt_treatment = st.selectbox(
        "Scheduled-receipt treatment",
        RECEIPT_TREATMENTS,
        format_func=lambda value: {
            "full": "Use full scheduled quantity",
            "risk_adjusted": "Adjust by supplier OTIF rate",
        }[value],
    )

    st.subheader("Starting raw-material inventory")
    starting_inventory: dict[str, int] = {}
    material_columns = st.columns(3)
    for index, (component_sku, component) in enumerate(COMPONENTS.items()):
        with material_columns[index % 3]:
            starting_inventory[component_sku] = int(
                st.number_input(
                    f"Starting material — {component_sku}",
                    min_value=0,
                    value=DEFAULT_MATERIAL_INVENTORY[component_sku],
                    step=50,
                    help=f"{component.name}, measured in {component.unit}.",
                )
            )

    inputs = prepare_procurement_inputs(
        fred_records,
        assumptions,
        finished_goods_policy,
        forecast_origin=forecast_origin,
    )
    policy = ProcurementPolicy(
        starting_inventory=starting_inventory,
        safety_stock_method=method,
        percentage=float(percentage),
        service_level=service_level,
        receipt_treatment=receipt_treatment,
    )
    records = build_procurement_plan(
        inputs.material_requirements,
        inputs.supplier_performance,
        inputs.material_error_stats,
        policy,
        forecast_origin=forecast_origin,
    )
    summary = summarize_procurement_plan(records)
    actions, past_due, release_now, risk = st.columns(4)
    actions.metric("Material purchase actions", summary.purchase_action_count)
    past_due.metric("Past-due releases", summary.past_due_action_count)
    release_now.metric("Release-now actions", summary.release_now_action_count)
    risk.metric("Risk-adjusted receipts", summary.receipt_at_risk_count)

    st.subheader("Supplier performance from static delivery history")
    st.dataframe(
        [
            {
                "component_sku": item.component_sku,
                "supplier": item.supplier_name,
                "deliveries": item.delivery_count,
                "average_actual_lead_months": item.average_actual_lead_months,
                "lead_time_standard_deviation": item.lead_time_standard_deviation,
                "on_time_rate": item.on_time_rate,
                "fill_rate": item.fill_rate,
                "otif_rate": item.otif_rate,
            }
            for item in inputs.supplier_performance
        ],
        hide_index=True,
        width="stretch",
        column_config={
            "component_sku": "Component SKU",
            "supplier": "Supplier",
            "deliveries": "Deliveries",
            "average_actual_lead_months": st.column_config.NumberColumn(
                "Average actual lead (months)", format="%.2f"
            ),
            "lead_time_standard_deviation": st.column_config.NumberColumn(
                "Lead-time SD", format="%.2f"
            ),
            "on_time_rate": st.column_config.NumberColumn(
                "On-time rate", format="percent"
            ),
            "fill_rate": st.column_config.NumberColumn(
                "Fill rate", format="percent"
            ),
            "otif_rate": st.column_config.NumberColumn(
                "OTIF rate", format="percent"
            ),
        },
    )

    st.subheader("Material safety-stock comparison")
    comparisons = compare_safety_stock(
        inputs.material_requirements,
        inputs.material_error_stats,
        inputs.supplier_performance,
        percentage=float(percentage),
        service_level=service_level,
    )
    st.dataframe(
        [
            {
                "component_sku": item.component_sku,
                "component_name": item.component_name,
                "average_monthly_requirement": item.average_monthly_requirement,
                "forecast_error_standard_deviation": (
                    item.forecast_error_standard_deviation
                ),
                "average_actual_lead_months": item.average_actual_lead_months,
                "lead_time_standard_deviation": (
                    item.lead_time_standard_deviation
                ),
                "none_target_units": item.none_target_units,
                "percentage_target_units": item.percentage_target_units,
                "statistical_target_units": item.statistical_target_units,
            }
            for item in comparisons
        ],
        hide_index=True,
        width="stretch",
        column_config={
            "component_sku": "Component SKU",
            "component_name": "Component",
            "average_monthly_requirement": st.column_config.NumberColumn(
                "Average monthly requirement", format="%.1f"
            ),
            "forecast_error_standard_deviation": st.column_config.NumberColumn(
                "Forecast-error SD", format="%.1f"
            ),
            "average_actual_lead_months": st.column_config.NumberColumn(
                "Average lead", format="%.2f"
            ),
            "lead_time_standard_deviation": st.column_config.NumberColumn(
                "Lead-time SD", format="%.2f"
            ),
            "none_target_units": "No safety stock",
            "percentage_target_units": "Percentage target",
            "statistical_target_units": "Statistical target",
        },
    )

    component_sku = st.selectbox(
        "Procurement component",
        tuple(COMPONENTS),
        format_func=lambda value: f"{value} - {COMPONENTS[value].name}",
    )
    selected = filter_procurement_plan(records, component_sku=component_sku)
    st.subheader("Material requirements and purchase recommendations")
    st.line_chart(
        [
            {
                "period": row["period"],
                "gross_requirement": row["gross_requirement_units"],
                "net_purchase_receipt": row["net_purchase_receipt_units"],
                "projected_ending_inventory": row[
                    "projected_ending_inventory_units"
                ],
            }
            for row in selected
        ],
        x="period",
        y=(
            "gross_requirement",
            "net_purchase_receipt",
            "projected_ending_inventory",
        ),
    )
    st.dataframe(selected, hide_index=True, width="stretch")

    example = selected[0]
    with st.expander("Show the first material purchase calculation"):
        st.code(
            "net purchase receipt = max(0, gross requirement + safety target "
            "- inventory position)",
            language="text",
        )
        st.write(
            f"For {example['period']}: max(0, "
            f"{example['gross_requirement_units']} + "
            f"{example['safety_stock_target_units']} - "
            f"{example['inventory_position_units']}) = "
            f"{example['net_purchase_receipt_units']} "
            f"{example['unit']}. Release recommendation: "
            f"{example['recommended_order_release_period']} "
            f"({example['release_status']})."
        )
    st.warning(
        "The statistical method uses a small fictional history and a normal-model "
        "approximation. Risk-adjusted receipts are expected availability, not a "
        "guarantee. This plan does not automatically issue orders or reschedule "
        "production around shortages."
    )
    return inputs


def _render_capacity_plan(
    inputs: ProcurementInputs,
    forecast_origin: str,
) -> None:
    """Render finite monthly work-center capacity and deferred production."""

    st.header("Capacity and constrained production plan")
    st.write(
        "This view converts the Inventory plan's net production requirements into "
        "work-center hours, compares them with effective capacity, and carries "
        "unbuilt units forward as deferred production."
    )
    st.caption(
        f"The plan follows forecast origin {forecast_origin}. Shared Window "
        "Assembly capacity is allocated proportionally by requested runtime; "
        "whole-unit output is rounded down."
    )

    calendar_columns = st.columns(4)
    with calendar_columns[0]:
        working_days = st.slider(
            "Working days per month",
            min_value=1,
            max_value=31,
            value=DEFAULT_WORKING_DAYS,
        )
    with calendar_columns[1]:
        shifts_per_day = st.slider(
            "Shifts per day",
            min_value=1,
            max_value=3,
            value=DEFAULT_SHIFTS_PER_DAY,
        )
    with calendar_columns[2]:
        hours_per_shift = st.slider(
            "Hours per shift",
            min_value=4.0,
            max_value=12.0,
            value=DEFAULT_HOURS_PER_SHIFT,
            step=0.5,
        )
    with calendar_columns[3]:
        downtime_percent = st.slider(
            "Planned downtime (%)",
            min_value=0,
            max_value=50,
            value=int(DEFAULT_DOWNTIME_PERCENT),
            step=5,
        )

    setup_hours = st.slider(
        "Setup hours per active product",
        min_value=0.0,
        max_value=16.0,
        value=DEFAULT_SETUP_HOURS,
        step=1.0,
    )
    window_overtime, door_overtime = st.columns(2)
    with window_overtime:
        window_overtime_hours = st.slider(
            "Window Assembly overtime hours",
            min_value=0,
            max_value=40,
            value=0,
            step=4,
        )
    with door_overtime:
        door_overtime_hours = st.slider(
            "Door Assembly overtime hours",
            min_value=0,
            max_value=40,
            value=0,
            step=4,
        )

    st.subheader("Product run rates")
    run_rates: dict[str, float] = {}
    rate_columns = st.columns(3)
    for column, (product_sku, product_name) in zip(rate_columns, PRODUCTS.items()):
        with column:
            run_rates[product_sku] = float(
                st.number_input(
                    f"Run rate — {product_sku}",
                    min_value=0.1,
                    value=DEFAULT_RUN_RATES[product_sku],
                    step=0.5,
                    help=f"{product_name}, measured in units per hour.",
                )
            )

    policy = CapacityPolicy(
        working_days_per_month=working_days,
        shifts_per_day=shifts_per_day,
        hours_per_shift=hours_per_shift,
        planned_downtime_percent=float(downtime_percent),
        setup_hours_per_active_product=setup_hours,
        overtime_hours={
            "WINDOW-ASSEMBLY": float(window_overtime_hours),
            "DOOR-ASSEMBLY": float(door_overtime_hours),
        },
        run_rates=run_rates,
    )
    plan = build_capacity_plan(
        inputs.inventory_plan,
        policy,
        forecast_origin=forecast_origin,
    )
    summary = summarize_capacity_plan(plan)
    overloads, deferred, utilization, planned = st.columns(4)
    overloads.metric(
        "Overloaded work-center months",
        summary.overloaded_work_center_months,
    )
    deferred.metric("Ending deferred production", f"{summary.ending_deferred_units:,}")
    utilization.metric(
        "Maximum required utilization",
        f"{summary.maximum_required_utilization_percent:.1f}%",
    )
    planned.metric("Planned production units", f"{summary.planned_production_units:,}")

    work_center_id = st.selectbox(
        "Capacity work center",
        tuple(WORK_CENTERS),
        format_func=lambda value: WORK_CENTERS[value],
    )
    selected_centers = filter_work_centers(
        plan.work_centers,
        work_center_id=work_center_id,
    )
    st.subheader("Required versus effective hours")
    st.line_chart(
        [
            {
                "period": row["period"],
                "required_hours": row["required_hours"],
                "effective_capacity_hours": row["effective_capacity_hours"],
            }
            for row in selected_centers
        ],
        x="period",
        y=("required_hours", "effective_capacity_hours"),
    )
    st.dataframe(selected_centers, hide_index=True, width="stretch")

    eligible_products = tuple(
        product_sku
        for product_sku in PRODUCTS
        if plan.products
        and next(
            row["work_center_id"]
            for row in plan.products
            if row["product_sku"] == product_sku
        )
        == work_center_id
    )
    product_sku = st.selectbox(
        "Capacity product",
        eligible_products,
        format_func=lambda value: f"{value} - {PRODUCTS[value]}",
    )
    selected_products = filter_capacity_products(
        plan.products,
        product_sku=product_sku,
    )
    st.subheader("Requested, planned, and deferred units")
    st.line_chart(
        [
            {
                "period": row["period"],
                "total_requested": row["total_requested_units"],
                "planned_production": row["planned_production_units"],
                "ending_deferred": row["ending_deferred_units"],
            }
            for row in selected_products
        ],
        x="period",
        y=("total_requested", "planned_production", "ending_deferred"),
    )
    st.dataframe(selected_products, hide_index=True, width="stretch")

    example = selected_centers[0]
    with st.expander("Show the first work-center calculation"):
        st.code(
            "effective capacity = regular hours x (1 - downtime %) + overtime\n"
            "capacity gap = effective capacity - required hours",
            language="text",
        )
        st.write(
            f"For {example['period']}, {example['work_center_name']} has "
            f"{example['effective_capacity_hours']:.1f} effective hours and "
            f"requires {example['required_hours']:.1f}. Its capacity gap is "
            f"{example['capacity_gap_hours']:+.1f} hours, so overload is "
            f"{'present' if example['overloaded'] else 'not present'}."
        )
    st.warning(
        "This is a monthly finite-capacity teaching plan, not detailed job "
        "sequencing. Deferred production is not automatically reflected back into "
        "finished-goods inventory or material purchase timing."
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
