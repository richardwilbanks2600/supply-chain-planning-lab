"""Maintained learner definitions and teaching comparisons for the dashboard."""

from dataclasses import dataclass


TEXTBOOK_NAME = "Operations and Supply Chain Management"
TEXTBOOK_VERSION = "7th Edition"


@dataclass(frozen=True)
class LearningTerm:
    """One searchable definition with optional calculation teaching aids."""

    key: str
    term: str
    section: str
    short: str
    detail: str
    dashboard_tab: str
    formula: str = ""
    example: str = ""
    common_mistake: str = ""
    keywords: tuple[str, ...] = ()


@dataclass(frozen=True)
class ForecastMethodLesson:
    """One moving-average family member and its learning trade-off."""

    name: str
    formula: str
    responsiveness: str
    smoothing: str
    best_teaching_use: str
    caution: str


TERMS = (
    LearningTerm(
        "fred_permit",
        "FRED PERMIT series",
        "Source data",
        "A national building-permit market indicator published through FRED.",
        "PERMIT measures authorized privately owned housing units. It provides "
        "outside context; it does not contain this fictional company's orders.",
        "Demand signal",
        common_mistake="Treating a national permit series as company sales.",
        keywords=("permits", "external", "market", "source"),
    ),
    LearningTerm(
        "saar",
        "Seasonally adjusted annual rate (SAAR)",
        "Source data",
        "An annualized pace adjusted for recurring seasonal patterns.",
        "A monthly SAAR value describes the annual pace implied by that month. "
        "It is not the count that occurred in that single month.",
        "Demand signal",
        formula="monthly housing pace = SAAR thousands x 1,000 / 12",
        example="A value of 1,500 implies a monthly pace near 125,000 homes.",
        common_mistake="Reading 1,500 as 1,500 permits or 1.5 million monthly permits.",
        keywords=("unit", "pace", "seasonal", "annualized"),
    ),
    LearningTerm(
        "market_signal",
        "Market signal",
        "Demand",
        "Outside information used as an input to a business assumption.",
        "A signal can help explain market direction without being a customer "
        "order, a company forecast, or proof of causation.",
        "Demand signal",
        common_mistake="Assuming correlation establishes customer demand.",
        keywords=("driver", "external", "indicator"),
    ),
    LearningTerm(
        "monthly_housing_pace",
        "Monthly housing pace",
        "Demand",
        "The FRED annualized pace converted to an approximate monthly rate.",
        "This rate conversion makes the external series compatible with the "
        "project's monthly time scale.",
        "Demand signal",
        formula="monthly pace = FRED SAAR thousands x 1,000 / 12",
        keywords=("month", "rate", "conversion"),
    ),
    LearningTerm(
        "demand_lag",
        "Demand lag",
        "Demand",
        "The delay between the permit signal and fictional requested ship demand.",
        "The approved three-month lag means a January permit value informs April "
        "company demand.",
        "Demand signal",
        formula="demand month = FRED month + 3 months",
        example="January permits are linked to April demand.",
        common_mistake="Using a future FRED value for an earlier demand month.",
        keywords=("lead", "delay", "driver period"),
    ),
    LearningTerm(
        "market_share",
        "Company market share",
        "Demand",
        "The fictional share of national monthly housing pace addressable by the company.",
        "This learner-controlled assumption scales an external national market "
        "pace down to the fictional company.",
        "Demand signal",
        formula="company homes = monthly housing pace x market share percent",
        common_mistake="Entering 10 when the intended share is 0.10%.",
        keywords=("share", "percent", "addressable"),
    ),
    LearningTerm(
        "customer_allocation",
        "Customer allocation",
        "Demand",
        "The percentage of product demand assigned to each fictional customer.",
        "All customer allocations must total 100%. Whole units are assigned "
        "with the same repeatable rounding rule so allocated demand still equals "
        "the product total.",
        "Demand signal",
        formula="customer units = product demand x customer allocation",
        common_mistake="Treating allocation as additional demand instead of a split.",
        keywords=("customer", "builder", "distributor", "remodeler"),
    ),
    LearningTerm(
        "units_per_home",
        "Units per home",
        "Demand",
        "The assumed number of one product associated with each addressable home.",
        "This attachment-rate assumption turns company homes into product demand.",
        "Demand signal",
        formula="product demand = company homes x units per home",
        keywords=("attachment", "product mix"),
    ),
    LearningTerm(
        "fred_expected_demand",
        "FRED-driven expected demand",
        "Demand",
        "Product demand implied by FRED and the visible business assumptions.",
        "This is the model's central expectation before company-specific variation. "
        "It keeps FRED directly connected to demand without claiming that a market "
        "indicator exactly equals company orders.",
        "Demand signal",
        formula="monthly pace x market share x units per home x customer allocation",
        common_mistake="Treating expected demand as realized company demand.",
        keywords=("baseline", "FRED", "expected", "market signal"),
    ),
    LearningTerm(
        "demand_realization_factor",
        "Static demand realization factor",
        "Demand",
        "A fixed product-month multiplier that moves realized demand around expectation.",
        "The committed factors combine company variation, mild product seasonality, "
        "small product-specific variation, and occasional unusual months. Most are "
        "within 15% of expectation and every factor stays between 0.75 and 1.25.",
        "Demand signal",
        formula="realized product demand = expected product demand x realization factor",
        example="Expected demand of 750 units with a 1.0582 factor becomes 794 units.",
        common_mistake="Assuming the factors are regenerated when the dashboard runs.",
        keywords=("static", "variation", "realized", "residual", "seasonality"),
    ),
    LearningTerm(
        "internal_demand",
        "Fictional internal demand",
        "Demand",
        "Whole realized product units generated from expectation and static variation.",
        "FRED and visible assumptions create expected demand. A committed static "
        "factor then creates realized teaching demand. The same inputs always "
        "produce the same values; they are not observed orders or shipments.",
        "Demand signal",
        formula=(
            "FRED-driven expected demand x static realization factor"
        ),
        common_mistake="Calling the generated values actual company sales.",
        keywords=("demand units", "synthetic", "fictional"),
    ),
    LearningTerm(
        "forecast_origin",
        "Forecast origin",
        "Forecasting",
        "The historical month treated as 'today' when making a forecast.",
        "The origin separates information considered available from values that "
        "are still unknown in the teaching backtest.",
        "Forecast",
        example="At a 2024-12 origin, 2025 months lie in the forecast horizon.",
        common_mistake="Using later realized values as if they were known at the origin.",
        keywords=("starting point", "as of", "backtest"),
    ),
    LearningTerm(
        "forecast_horizon",
        "Forecast horizon",
        "Forecasting",
        "How many months ahead of the forecast origin a value is predicted.",
        "Error often changes by horizon because less information is available "
        "farther into the future.",
        "Forecast",
        formula="horizon = demand month - forecast origin in months",
        keywords=("months ahead", "lead"),
    ),
    LearningTerm(
        "baseline_scenario",
        "Baseline scenario",
        "Planning workflow",
        "The dashboard's default assumptions used as a comparison reference.",
        "The baseline scenario uses the same forecast starting point as the "
        "working scenario. This isolates the effect of the learner's changed "
        "assumptions; it is not an industry target or forecast method.",
        "Overview",
        common_mistake="Confusing the default scenario with a baseline forecast method.",
        keywords=("defaults", "working scenario", "comparison", "reference"),
    ),
    LearningTerm(
        "baseline_forecast",
        "Baseline forecast",
        "Forecasting",
        "A simple benchmark that more complex methods should improve upon.",
        "Baselines are valuable because their logic is transparent. Complexity "
        "is useful only when it improves results enough to justify its cost.",
        "Forecast",
        common_mistake="Assuming a simple method is useless because it is simple.",
        keywords=("benchmark", "naive", "comparison"),
    ),
    LearningTerm(
        "previous_month",
        "Previous-month forecast",
        "Forecasting",
        "Uses the most recent realized demand as the next forecast.",
        "It reacts quickly but follows noise and can lag when demand changes "
        "direction repeatedly.",
        "Forecast",
        formula="forecast(t) = realized demand(t - 1)",
        keywords=("naive", "last value"),
    ),
    LearningTerm(
        "seasonal_naive",
        "Same-month-last-year forecast",
        "Forecasting",
        "Uses demand from the same calendar month one year earlier.",
        "This is the primary internal-history baseline because it preserves a "
        "simple annual seasonal comparison.",
        "Forecast",
        formula="forecast(t) = realized demand(t - 12 months)",
        common_mistake="Calling it a trend model; it only repeats last year's month.",
        keywords=("seasonal naive", "year", "primary"),
    ),
    LearningTerm(
        "moving_average",
        "Simple moving average",
        "Forecasting",
        "The unweighted mean of a fixed number of recent realized-demand values.",
        "Short windows respond faster; long windows smooth more short-lived movement. "
        "Every observation inside the window receives equal weight.",
        "Forecast",
        formula="forecast = sum of latest n realized-demand values / n",
        example="For 24, 30, and 36 units, a 3-month average forecasts 30.",
        common_mistake="Including the month being forecast in its own input window.",
        keywords=("rolling", "trailing", "average", "window"),
    ),
    LearningTerm(
        "weighted_moving_average",
        "Weighted moving average",
        "Forecasting",
        "An average that deliberately gives some recent periods more influence.",
        "Weights must be chosen and sum to one. More recent weight usually makes "
        "the forecast more responsive but less smooth.",
        "Learning Guide",
        formula="forecast = sum(weight(i) x realized(i)); weights sum to 1",
        common_mistake="Choosing weights after seeing test results without validation.",
        keywords=("rolling", "weights", "responsive"),
    ),
    LearningTerm(
        "exponential_smoothing",
        "Simple exponential smoothing",
        "Forecasting",
        "A forecast that updates its previous estimate using smoothing constant alpha.",
        "A high alpha gives the newest generated demand more influence. A low "
        "alpha keeps more of the previous forecast. This guide explains the method, "
        "but the planning model does not use it.",
        "Learning Guide",
        formula="forecast(t+1) = alpha x realized(t) + (1-alpha) x forecast(t)",
        common_mistake="Treating alpha as an automatically optimal business setting.",
        keywords=("alpha", "smoothing", "recursive"),
    ),
    LearningTerm(
        "smoothing_alpha",
        "Smoothing constant (alpha)",
        "Forecasting",
        "A value from 0 to 1 that controls how strongly a forecast reacts to new data.",
        "Values near 1 emphasize the newest generated demand. Values near 0 keep "
        "more of the previous forecast and produce a smoother series.",
        "Learning Guide",
        common_mistake="Assuming a higher alpha is always more accurate.",
        keywords=("exponential smoothing", "responsive", "weight"),
    ),
    LearningTerm(
        "rolling_origin",
        "Rolling-origin evaluation",
        "Forecasting",
        "Repeatedly moves the simulated forecast date forward and scores later outcomes.",
        "Each origin creates a new honest historical test using only the approved "
        "information treatment at that point.",
        "Forecast",
        common_mistake="Evaluating only one convenient forecast origin.",
        keywords=("backtest", "evaluation", "time series"),
    ),
    LearningTerm(
        "known_driver",
        "Known FRED driver",
        "Forecasting",
        "A lagged permit value already observed by the forecast origin.",
        "Because demand lags permits by three months, horizons one through three "
        "use driver values classified as known. Their forecast error can still be "
        "nonzero because realized company demand includes static variation that the "
        "forecast does not know.",
        "Forecast",
        common_mistake="Assuming a known market driver guarantees exact company demand.",
        keywords=("observed", "lagged", "horizon"),
    ),
    LearningTerm(
        "forecasted_driver",
        "Forecasted FRED driver",
        "Forecasting",
        "A future permit value not yet known at the forecast origin.",
        "Horizons four through twelve use a previous-month-naive FRED forecast.",
        "Forecast",
        common_mistake="Judging known-driver horizons as if they required a FRED forecast.",
        keywords=("unknown", "future", "permit"),
    ),
    LearningTerm(
        "generated_backtest_actual",
        "Generated realized demand used for backtest scoring",
        "Forecasting",
        "Fictional generated demand treated as the known outcome in a historical test.",
        "The project has no real company orders. Forecast tables therefore compare "
        "each estimate with the repeatable internal-demand value generated for that "
        "month and label that value clearly as generated demand.",
        "Forecast",
        common_mistake="Reading a generated realized value as a real customer order or shipment.",
        keywords=("actual", "synthetic", "fictional", "backtest", "generated demand"),
    ),
    LearningTerm(
        "forecast_error",
        "Forecast error",
        "Forecasting",
        "The signed difference between realized and forecast demand.",
        "The project uses realized demand minus forecast. Positive error means demand was "
        "underforecast; negative error means it was overforecast.",
        "Forecast",
        formula="error = realized demand - forecast demand",
        common_mistake="Switching the subtraction order when interpreting bias.",
        keywords=("actual", "difference", "underforecast", "overforecast"),
    ),
    LearningTerm(
        "mae",
        "Mean absolute error (MAE)",
        "Forecasting",
        "The average size of forecast errors without regard to direction.",
        "MAE is expressed in the same units as demand, making it easy to interpret. "
        "Lower is better when comparing the same data and scale.",
        "Forecast",
        formula="MAE = sum(abs(realized demand - forecast)) / forecast count",
        common_mistake="Comparing MAE across products with very different demand scales.",
        keywords=("accuracy", "absolute", "metric"),
    ),
    LearningTerm(
        "bias",
        "Forecast bias",
        "Forecasting",
        "The average signed error, showing persistent forecast direction.",
        "Positive bias means underforecasting under this project's error convention; "
        "negative bias means overforecasting.",
        "Forecast",
        formula="bias = sum(realized demand - forecast) / forecast count",
        common_mistake="Reading a bias near zero as proof that individual errors are small.",
        keywords=("direction", "signed error"),
    ),
    LearningTerm(
        "inventory_position",
        "Inventory position",
        "Inventory",
        "Finished or material inventory available before the month's requirement.",
        "In this project it is beginning inventory plus usable scheduled receipts. "
        "There are no finished-goods scheduled receipts.",
        "Inventory",
        formula="inventory position = beginning inventory + usable receipts",
        keywords=("available", "on hand", "receipts"),
    ),
    LearningTerm(
        "safety_stock",
        "Safety stock",
        "Inventory",
        "Extra inventory targeted as protection against uncertainty.",
        "The finished-goods teaching policy uses a percentage of next month's "
        "forecast; this is a visible assumption, not an optimized recommendation.",
        "Inventory",
        common_mistake="Treating safety stock as demand that customers will consume.",
        keywords=("buffer", "protection", "target"),
    ),
    LearningTerm(
        "scheduled_receipt",
        "Scheduled receipt",
        "Inventory",
        "An order already expected to arrive in a future month.",
        "Material scheduled receipts come from fixed open purchase orders. The "
        "learner may count them fully or reduce them for supplier reliability.",
        "Materials and procurement",
        keywords=("open order", "incoming"),
    ),
    LearningTerm(
        "net_production_requirement",
        "Net production requirement",
        "Inventory",
        "What should be produced after inventory and safety stock are considered.",
        "This is an unconstrained requirement. Capacity planning later determines "
        "how much can actually be scheduled.",
        "Inventory",
        formula="max(0, forecast demand + safety target - inventory position)",
        example="718 demand + 189 safety - 300 available = 607 units required.",
        common_mistake="Calling the requirement a capacity-feasible schedule.",
        keywords=("production", "netting", "unconstrained"),
    ),
    LearningTerm(
        "projected_ending_inventory",
        "Projected ending inventory",
        "Inventory",
        "Expected stock remaining after the month's demand and planned supply.",
        "It becomes the next month's beginning inventory in the roll-forward.",
        "Inventory",
        formula=(
            "inventory position + net production requirement - forecast demand"
        ),
        keywords=("ending", "roll forward"),
    ),
    LearningTerm(
        "bom",
        "Bill of materials (BOM)",
        "Procurement",
        "The component quantities required to make one finished product.",
        "The BOM connects the production requirement to glass, vinyl, slabs, "
        "frames, and hardware purchasing needs.",
        "Materials and procurement",
        formula="component need = product units x component quantity per product",
        keywords=("recipe", "component", "explosion"),
    ),
    LearningTerm(
        "gross_material_requirement",
        "Gross material requirement",
        "Procurement",
        "Total component demand before inventory and receipts are subtracted.",
        "Requirements from every finished product sharing a component are combined.",
        "Materials and procurement",
        keywords=("component need", "BOM"),
    ),
    LearningTerm(
        "lead_time",
        "Supplier lead time",
        "Procurement",
        "The elapsed months between placing an order and receiving it.",
        "The plan shifts a required receipt backward by planned lead time to find "
        "the recommended order-release month.",
        "Materials and procurement",
        formula="release month = receipt month - planned lead months",
        keywords=("supplier", "release", "delivery"),
    ),
    LearningTerm(
        "on_time_rate",
        "On-time rate",
        "Supplier performance",
        "The share of deliveries arriving within promised lead time.",
        "A delivery may be on time but incomplete, so on-time rate alone does not "
        "measure full delivery performance.",
        "Materials and procurement",
        formula="on-time deliveries / all deliveries",
        keywords=("supplier", "delivery"),
    ),
    LearningTerm(
        "fill_rate",
        "Fill rate",
        "Supplier performance",
        "Received quantity divided by ordered quantity.",
        "The project caps the aggregate measure at the complete ordered quantity; "
        "timing is evaluated separately.",
        "Materials and procurement",
        formula="received quantity / ordered quantity",
        keywords=("supplier", "quantity", "complete"),
    ),
    LearningTerm(
        "otif",
        "On time in full (OTIF)",
        "Supplier performance",
        "The share of deliveries that were both timely and complete.",
        "OTIF combines the two conditions for each delivery. The risk-adjusted "
        "scenario uses historical OTIF to reduce credited open-order quantities.",
        "Materials and procurement",
        formula="deliveries both on time and in full / all deliveries",
        common_mistake="Multiplying aggregate on-time rate by aggregate fill rate.",
        keywords=("supplier", "reliability", "risk"),
    ),
    LearningTerm(
        "material_safety_stock",
        "Material safety stock",
        "Procurement",
        "Extra component inventory targeted as protection against uncertainty.",
        "The learner can choose no extra material, a percentage of next month's "
        "need, or a statistical method. Only the inputs belonging to the selected "
        "method affect the plan.",
        "Materials and procurement",
        common_mistake="Changing a percentage or service level that is inactive for the selected method.",
        keywords=("buffer", "component", "method", "policy"),
    ),
    LearningTerm(
        "percentage_material_safety_stock",
        "Percentage material safety stock",
        "Procurement",
        "A material buffer set as a percentage of the following month's requirement.",
        "This simple teaching policy applies only when Percentage of next month's "
        "need is the selected material safety-stock method.",
        "Materials and procurement",
        formula="target = following-month material requirement x selected percentage",
        common_mistake="Expecting this percentage to affect the statistical method.",
        keywords=("buffer", "component", "percent", "next month"),
    ),
    LearningTerm(
        "service_level",
        "Target material service level",
        "Procurement",
        "The desired probability used to choose a factor for statistical safety stock.",
        "This setting applies only to the statistical method. Higher service "
        "levels increase the buffer when demand or lead time varies, but they do "
        "not guarantee that every order will be filled.",
        "Materials and procurement",
        common_mistake="Interpreting 95% as 95% more inventory.",
        keywords=("z value", "probability", "safety stock", "factor"),
    ),
    LearningTerm(
        "standard_deviation",
        "Standard deviation",
        "Procurement",
        "A measure of how far values typically spread from their average.",
        "A larger standard deviation means the historical errors or lead times "
        "varied more, which increases this project's statistical safety stock.",
        "Learning Guide",
        common_mistake="Treating a larger value as better performance.",
        keywords=("variation", "spread", "statistics", "safety stock"),
    ),
    LearningTerm(
        "variance",
        "Variance",
        "Procurement",
        "Standard deviation multiplied by itself.",
        "The statistical safety-stock formula combines variance from forecast "
        "error and supplier lead time before taking a square root.",
        "Learning Guide",
        formula="variance = standard deviation x standard deviation",
        common_mistake="Comparing variance directly with demand units; its units are squared.",
        keywords=("variation", "spread", "statistics", "squared"),
    ),
    LearningTerm(
        "service_factor",
        "Service-level factor (z)",
        "Procurement",
        "A multiplier linked to the selected target service level.",
        "The project looks up this factor from the chosen service level and uses "
        "it to scale statistical safety stock. A higher target uses a larger factor.",
        "Learning Guide",
        common_mistake="Interpreting z as a percentage of extra inventory.",
        keywords=("z value", "probability", "multiplier", "normal"),
    ),
    LearningTerm(
        "statistical_safety_stock",
        "Statistical material safety stock",
        "Procurement",
        "A buffer combining demand-error and supplier lead-time variability.",
        "The formula combines typical forecast error, average demand, supplier "
        "lead-time variation, and the selected service-level factor. It is a "
        "teaching comparison, not an optimized purchasing policy.",
        "Materials and procurement",
        formula=(
            "service-level factor x square root(average lead time x "
            "demand-error variance + average demand squared x lead-time variance)"
        ),
        common_mistake="Using the formula without checking assumptions or data quality.",
        keywords=("variability", "z", "buffer"),
    ),
    LearningTerm(
        "risk_adjusted_receipt",
        "Risk-adjusted scheduled receipt",
        "Procurement",
        "An open order credited at less than full quantity using supplier OTIF.",
        "This scenario makes delivery risk visible before planning purchases; it "
        "does not change the supplier's actual open order.",
        "Materials and procurement",
        formula="usable receipt = scheduled receipt x supplier OTIF",
        keywords=("open order", "supplier", "usable"),
    ),
    LearningTerm(
        "purchase_receipt",
        "Net purchase receipt",
        "Procurement",
        "The component quantity recommended to arrive in the requirement month.",
        "It is calculated after netting material inventory, usable scheduled "
        "receipts, and the selected safety-stock target.",
        "Materials and procurement",
        keywords=("buy", "material", "arrival"),
    ),
    LearningTerm(
        "order_release",
        "Recommended order release",
        "Procurement",
        "When a purchase should be placed so it can arrive by its need month.",
        "The date is a monthly teaching offset, not a day-level supplier promise.",
        "Materials and procurement",
        formula="receipt period shifted earlier by planned lead time",
        keywords=("purchase order", "timing"),
    ),
    LearningTerm(
        "past_due_release",
        "Past-due order release",
        "Procurement",
        "A recommended release month earlier than the forecast origin.",
        "It flags a timing exception caused by requirement timing and lead time. "
        "It does not prove that a real supplier order is late.",
        "Materials and procurement",
        keywords=("exception", "late", "release"),
    ),
    LearningTerm(
        "sku",
        "Stock keeping unit (SKU)",
        "Planning workflow",
        "A short code used to identify one product or material.",
        "Codes such as WIN-2436 and GLASS-SQFT keep records unambiguous. The "
        "dashboard pairs each code with a plain-language product or component name.",
        "All planning tabs",
        common_mistake="Treating the code as a quantity or product dimension without reading its name.",
        keywords=("product code", "material code", "identifier"),
    ),
    LearningTerm(
        "work_center",
        "Work center",
        "Capacity",
        "A grouped production resource with shared available hours.",
        "Both window products use Window Assembly; the exterior door uses Door "
        "Assembly. Products sharing a center compete for the same capacity.",
        "Capacity",
        keywords=("factory", "resource", "line"),
    ),
    LearningTerm(
        "regular_capacity",
        "Regular capacity hours",
        "Capacity",
        "Calendar hours available before downtime and overtime adjustments.",
        "The monthly calendar is intentionally simple and does not schedule "
        "individual employees or machines.",
        "Capacity",
        formula="working days x shifts per day x hours per shift",
        keywords=("calendar", "hours", "shifts"),
    ),
    LearningTerm(
        "effective_capacity",
        "Effective capacity hours",
        "Capacity",
        "Regular hours after planned downtime plus approved overtime.",
        "Setup and product runtime must fit within these hours.",
        "Capacity",
        formula="regular hours x (1 - downtime %) + overtime hours",
        keywords=("available", "downtime", "overtime"),
    ),
    LearningTerm(
        "planned_downtime",
        "Planned downtime",
        "Capacity",
        "The percentage of regular hours reserved as unavailable.",
        "It represents expected maintenance, breaks, or other planned losses in "
        "one visible teaching assumption.",
        "Capacity",
        common_mistake="Adding downtime hours to available capacity.",
        keywords=("maintenance", "loss", "percent"),
    ),
    LearningTerm(
        "setup_time",
        "Setup hours",
        "Capacity",
        "Time required to prepare a work center for each active product.",
        "Setup consumes capacity before product runtime. The monthly model does "
        "not sequence individual production runs.",
        "Capacity",
        formula="setup hours per product x active product count",
        keywords=("changeover", "active product"),
    ),
    LearningTerm(
        "run_rate",
        "Run rate",
        "Capacity",
        "Finished product units produced per runtime hour.",
        "A higher run rate requires fewer hours for the same units. It is a "
        "learner assumption, not measured factory performance.",
        "Capacity",
        formula="requested runtime = requested units / units per hour",
        keywords=("speed", "units per hour", "runtime"),
    ),
    LearningTerm(
        "required_utilization",
        "Required utilization",
        "Capacity",
        "Requested setup and runtime divided by effective capacity.",
        "Above 100% means the requested work does not fit in the available hours.",
        "Capacity",
        formula="required hours / effective capacity hours x 100",
        common_mistake="Reading utilization above 100% as achieved output.",
        keywords=("load", "percent", "hours"),
    ),
    LearningTerm(
        "overload",
        "Capacity overload",
        "Capacity",
        "A month when required hours exceed effective capacity hours.",
        "The plan flags overload explicitly and proportionally allocates the "
        "runtime that remains after setup.",
        "Capacity",
        formula="overloaded when required hours > effective hours",
        keywords=("constraint", "shortage", "exception"),
    ),
    LearningTerm(
        "capacity_factor",
        "Capacity factor",
        "Capacity",
        "The share of requested runtime that can fit after setup hours.",
        "A factor below one proportionally reduces each active product before "
        "whole-unit rounding.",
        "Capacity",
        formula="min(1, available runtime / requested runtime)",
        keywords=("allocation", "proportion"),
    ),
    LearningTerm(
        "capacity_feasible_production",
        "Capacity-feasible production",
        "Capacity",
        "Whole units the work center can schedule within effective hours.",
        "It is deliberately shown beside the unconstrained requirement so the "
        "learner can see rather than hide the factory constraint.",
        "Capacity",
        common_mistake="Assuming every production requirement automatically gets built.",
        keywords=("planned", "scheduled", "output"),
    ),
    LearningTerm(
        "deferred_production",
        "Deferred production",
        "Capacity",
        "Requested units that could not be built and carry into the next month.",
        "Deferred units are backlog within the teaching horizon. They are not "
        "cancelled demand and are not silently removed.",
        "Capacity",
        formula="ending deferred = requested units - planned production",
        common_mistake="Treating deferred units as lost or cancelled orders.",
        keywords=("backlog", "unbuilt", "carryover"),
    ),
)


FORECAST_METHOD_LESSONS = (
    ForecastMethodLesson(
        "2-month simple moving average",
        "(A[t-1] + A[t-2]) / 2",
        "High: recent changes affect the forecast quickly.",
        "Low: short-lived variation remains visible.",
        "Showing why short windows follow turning points sooner.",
        "Can chase noise and reverse direction frequently.",
    ),
    ForecastMethodLesson(
        "3-month simple moving average",
        "(A[t-1] + A[t-2] + A[t-3]) / 3",
        "Moderate: balances recent movement with some history.",
        "Moderate: dampens more variation than a 2-month window.",
        "The project's implemented rolling-average baseline.",
        "Still lags sustained increases or decreases.",
    ),
    ForecastMethodLesson(
        "6-month simple moving average",
        "sum(A[t-1] through A[t-6]) / 6",
        "Low: a new observation changes only one-sixth of the average.",
        "High: produces a steadier line.",
        "Demonstrating the smoothing-versus-responsiveness trade-off.",
        "May respond too slowly when demand changes level.",
    ),
    ForecastMethodLesson(
        "Weighted moving average",
        "sum(w[i] x A[t-i]); weights sum to 1",
        "Chosen by the weights; heavier recent weights react faster.",
        "Chosen by the weights; spread weights create more smoothing.",
        "Teaching that not every historical month must count equally.",
        "Weights add judgment and can be tuned to historical noise.",
    ),
    ForecastMethodLesson(
        "Simple exponential smoothing",
        "F[t+1] = alpha x A[t] + (1-alpha) x F[t]",
        "High when alpha is near 1; low when alpha is near 0.",
        "High when alpha is low because older information decays slowly.",
        "Showing a compact recursive alternative to a fixed window.",
        "The starting forecast and alpha choice affect results.",
    ),
)


_TERMS_BY_KEY = {item.key: item for item in TERMS}
if len(_TERMS_BY_KEY) != len(TERMS):
    raise RuntimeError("Learning-term keys must be unique.")


def learning_term(key: str) -> LearningTerm:
    """Return one maintained term or raise a clear error for an unknown key."""

    try:
        return _TERMS_BY_KEY[key]
    except KeyError as exc:
        raise KeyError(f"Unknown learning term {key!r}.") from exc


def help_text(key: str) -> str:
    """Return the concise tooltip definition for a maintained term."""

    return learning_term(key).short


def learning_sections() -> tuple[str, ...]:
    """Return unique glossary sections in maintained display order."""

    return tuple(dict.fromkeys(item.section for item in TERMS))


def search_learning_terms(
    query: str = "", *, section: str | None = None
) -> list[LearningTerm]:
    """Filter terms by plain-text query and optional exact section."""

    normalized = query.casefold().strip()
    matches = []
    for item in TERMS:
        if section and item.section != section:
            continue
        searchable = " ".join(
            (
                item.term,
                item.short,
                item.detail,
                item.formula,
                item.example,
                item.common_mistake,
                *item.keywords,
            )
        ).casefold()
        if not normalized or normalized in searchable:
            matches.append(item)
    return matches
