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
from supply_chain_planning_lab.materials import (
    BOM,
    COMPONENTS,
    DEFAULT_MATERIAL_INVENTORY,
)
from supply_chain_planning_lab.planning_workflow import prepare_procurement_inputs
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
    (
        demand_tab,
        forecast_tab,
        fred_forecast_tab,
        inventory_tab,
        procurement_tab,
        external_tab,
    ) = st.tabs(
        (
            "Internal demand",
            "Forecast baselines",
            "FRED-informed forecast",
            "Inventory plan",
            "Materials and procurement",
            "External market indicator",
        )
    )
    with demand_tab:
        scenario = _render_internal_demand()
    with forecast_tab:
        if scenario is not None:
            _render_forecast_baselines(scenario[1])
    with fred_forecast_tab:
        if scenario is not None:
            _render_fred_informed_forecast(*scenario)
    with inventory_tab:
        if scenario is not None:
            inventory_scenario = _render_inventory_plan(scenario[0], scenario[2])
    with procurement_tab:
        if scenario is not None:
            _render_procurement_plan(
                scenario[0],
                scenario[2],
                inventory_scenario[0],
                inventory_scenario[1],
            )
    with external_tab:
        _render_external_indicator()


def _render_internal_demand() -> tuple[
    list[ProcessedObservation], list[DemandRecord], DemandAssumptions
] | None:
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
    return fred_records, records, assumptions


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
        "to calculate internal demand."
    )
    st.caption(
        "Demand horizons 1-3 use already-observed lagged permit values. Horizons "
        f"4-{MAX_FORECAST_HORIZON} forecast the unknown permit driver with the "
        f"{DRIVER_METHOD_LABEL.lower()}."
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
            "This is zero by construction because the demand driver is already "
            "known; it demonstrates calculation mechanics, not predictive skill."
        ),
    )
    forecasted_count.metric(
        "Forecasted-driver forecasts", forecasted.forecast_count
    )
    forecasted_mae.metric(
        "Forecasted-driver MAE",
        f"{forecasted.mean_absolute_error:,.1f}",
        help="Mean absolute product-demand error where the FRED driver was unknown.",
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

    st.subheader("Actual versus FRED-informed forecast")
    st.line_chart(
        [
            {
                "demand_period": record["demand_period"],
                "actual_units": record["actual_demand_units"],
                "forecast_units": record["forecast_demand_units"],
            }
            for record in selected
        ],
        x="demand_period",
        y=("actual_units", "forecast_units"),
    )
    st.dataframe(selected, hide_index=True, width="stretch")

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
) -> None:
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
